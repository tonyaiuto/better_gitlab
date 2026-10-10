"""Turning selected presubmit blocks into a plan of actions and test runs.

Actions:
  - An action runs once per machine type (its own, or the defaults).
  - The same action on the same machine type, selected by several blocks,
    runs once, with the union of their files.
  - The command is then expanded: {FILES} becomes all the files, {EACH_FILE}
    makes one command per file. File names are shell-quoted.
  - Deleted files still select actions, but are left out of {FILES} and
    {EACH_FILE}. An action whose command needs files, selected only by
    deleted files, gets no commands.

Test suites:
  - A suite runs once per platform (or once with no platform).
  - Suites with the same test_args and platform are merged into one test run
    with the union of their test patterns.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass

from presubmit import loader

DEFAULT_MACHINE_TYPES = ["default"]

FILES = "{FILES}"
EACH_FILE = "{EACH_FILE}"


class PlanError(Exception):
    """The selected actions or test suites cannot be planned."""


@dataclass
class PlannedAction:
    name: str
    machine_type: str
    # The files that selected this action, sorted. Includes deleted files.
    files: list
    # The expanded commands to run, in order. Empty if the command uses
    # {FILES} or {EACH_FILE} and every selecting file was deleted.
    commands: list


@dataclass
class TestRun:
    # "" means no platform was given.
    platform: str
    test_args: list
    # Bazel test patterns, sorted and unique.
    tests: list
    # Names of the suites merged into this run, sorted.
    suites: list
    # If true, run `bazel coverage` instead of `bazel test`.
    coverage: bool


@dataclass
class Plan:
    # Sorted by (name, machine_type).
    actions: list
    # Sorted by (platform, test_args).
    test_runs: list


def expand_command(name: str, command: str, files: list) -> list:
    """Returns the commands to run for an action over files."""
    has_files = FILES in command
    has_each_file = EACH_FILE in command
    if has_files and has_each_file:
        raise PlanError("action %r uses both %s and %s" % (name, FILES, EACH_FILE))
    if has_each_file:
        return [command.replace(EACH_FILE, shlex.quote(f)) for f in files]
    if has_files:
        if not files:
            return []
        return [command.replace(FILES, " ".join(shlex.quote(f) for f in files))]
    return [command]


def build_plan(
    loaded: loader.Loaded,
    selections: list,
    default_machine_types: list = DEFAULT_MACHINE_TYPES,
    deleted_files=(),
) -> Plan:
    """Builds the plan for the selections made from loaded.

    deleted_files are left out of command expansion (see the module doc).
    """
    deleted = set(deleted_files)
    # (action name, machine type) -> set of files
    action_files = {}
    # (tuple(test_args), platform, coverage) -> (set of test patterns, set of suite names)
    test_groups = {}

    for selected in selections:
        for name in selected.actions:
            action = loaded.actions[name]
            for machine_type in list(action.machine_type) or default_machine_types:
                action_files.setdefault((name, machine_type), set()).update(
                    selected.files
                )
        for name in selected.test_suites:
            suite = loaded.test_suites[name]
            for platform in list(suite.platform) or [""]:
                key = (tuple(suite.test_args), platform, suite.coverage)
                tests, suites = test_groups.setdefault(key, (set(), set()))
                tests.update(suite.tests)
                suites.add(name)

    actions = []
    for (name, machine_type), files in sorted(action_files.items()):
        sorted_files = sorted(files)
        actions.append(
            PlannedAction(
                name=name,
                machine_type=machine_type,
                files=sorted_files,
                commands=expand_command(
                    name,
                    loaded.actions[name].command,
                    [f for f in sorted_files if f not in deleted],
                ),
            )
        )

    test_runs = []
    for (test_args, platform, coverage), (tests, suites) in sorted(
        test_groups.items(), key=lambda item: (item[0][1], item[0][0], item[0][2])
    ):
        test_runs.append(
            TestRun(
                platform=platform,
                test_args=list(test_args),
                tests=sorted(tests),
                suites=sorted(suites),
                coverage=coverage,
            )
        )

    return Plan(actions=actions, test_runs=test_runs)
