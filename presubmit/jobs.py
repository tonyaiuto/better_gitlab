"""Turning a Plan into jobs: what a CI system (GitLab first) would run.

run_actions jobs:
  - One job per machine type, named "actions:<machine type>", running every
    planned command for that machine type as one run_actions invocation.
  - An action with one command keeps its name. An action with several
    commands ({EACH_FILE}) becomes <name>.1, <name>.2, ... in file order.
  - Names are made legal for run_actions: characters outside [A-Za-z0-9_.-]
    become '_', and a name not starting with a letter or '_' gets a '_' prefix.
  - Actions with no commands (selected only by deleted files) are left out,
    and a machine type with no commands left gets no job.

bazel jobs:
  - One job per test run: `bazel test` or, for coverage suites,
    `bazel coverage`, with --platforms=<platform> when the run has one, then
    the test args, then `--` and the test patterns.
  - Named "bazel:<test|coverage>[:<platform>]". When several test runs would
    share a name (they differ in test_args), ":1", ":2", ... are appended.
  - A test run with no patterns gets no job.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from presubmit import plan as plan_lib

RUN_ACTIONS_COMMAND = ["run_actions"]
BAZEL_COMMAND = ["bazel"]

RUN_ACTIONS = "run_actions"
BAZEL = "bazel"

_ILLEGAL_NAME_CHARS_RE = re.compile(r"[^A-Za-z0-9_.-]")


@dataclass
class JobAction:
    # The name given to run_actions.
    name: str
    # The TESTING action it came from.
    action: str
    command: str


@dataclass
class Job:
    name: str
    # RUN_ACTIONS or BAZEL.
    kind: str
    # The command line to run.
    argv: list
    # RUN_ACTIONS jobs only.
    machine_type: str = ""
    actions: list = field(default_factory=list)
    # BAZEL jobs only. "" means no platform was given.
    platform: str = ""
    tests: list = field(default_factory=list)
    suites: list = field(default_factory=list)


def run_actions_name(name: str) -> str:
    """Returns name, changed if needed so run_actions reads it as a name."""
    legal = _ILLEGAL_NAME_CHARS_RE.sub("_", name)
    if not re.match(r"[A-Za-z_]", legal):
        legal = "_" + legal
    return legal


def _run_actions_jobs(actions: list, run_actions_command: list) -> list:
    # machine type -> list of JobAction, in plan order (sorted by action name)
    by_machine = {}
    for planned in actions:
        if not planned.commands:
            continue
        base = run_actions_name(planned.name)
        job_actions = by_machine.setdefault(planned.machine_type, [])
        if len(planned.commands) == 1:
            job_actions.append(JobAction(base, planned.name, planned.commands[0]))
            continue
        for i, command in enumerate(planned.commands, 1):
            job_actions.append(JobAction("%s.%d" % (base, i), planned.name, command))
    jobs = []
    for machine_type, job_actions in sorted(by_machine.items()):
        argv = list(run_actions_command) + ["--"]
        argv += ["%s=%s" % (a.name, a.command) for a in job_actions]
        jobs.append(
            Job(
                name="actions:%s" % machine_type,
                kind=RUN_ACTIONS,
                argv=argv,
                machine_type=machine_type,
                actions=job_actions,
            )
        )
    return jobs


def _bazel_jobs(test_runs: list, bazel_command: list) -> list:
    runs = [r for r in test_runs if r.tests]
    names = []
    for run in runs:
        name = "bazel:%s" % ("coverage" if run.coverage else "test")
        if run.platform:
            name += ":" + run.platform
        names.append(name)
    jobs = []
    seen = {}
    for run, name in zip(runs, names):
        if names.count(name) > 1:
            seen[name] = seen.get(name, 0) + 1
            name = "%s:%d" % (name, seen[name])
        argv = list(bazel_command) + ["coverage" if run.coverage else "test"]
        if run.platform:
            argv.append("--platforms=%s" % run.platform)
        argv += list(run.test_args) + ["--"] + list(run.tests)
        jobs.append(
            Job(
                name=name,
                kind=BAZEL,
                argv=argv,
                platform=run.platform,
                tests=list(run.tests),
                suites=list(run.suites),
            )
        )
    return jobs


def build_jobs(
    plan: plan_lib.Plan,
    run_actions_command: list = RUN_ACTIONS_COMMAND,
    bazel_command: list = BAZEL_COMMAND,
) -> list:
    """Returns the jobs for plan: run_actions jobs, then bazel jobs, each sorted by name."""
    return _run_actions_jobs(plan.actions, run_actions_command) + sorted(
        _bazel_jobs(plan.test_runs, bazel_command), key=lambda j: j.name
    )
