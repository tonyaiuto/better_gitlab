"""Plans the jobs for a list of past PRs, to see what presubmit would have run.

The input is the JSON written by pr_test_history's pr_files.py: a list of

    {"pr": 57260, "title": ..., "merge_commit_sha": ..., "merged_at": ...,
     "files": [{"filename": ..., "status": "modified", "previous_filename": ...}]}

where status is GitHub's ("added", "modified", "removed", "renamed", ...).
Each PR's changed files are its filenames plus the previous_filename of
renames; the deleted files are the "removed" ones plus those previous
filenames. That matches GitDiffChangedFiles, which reports a rename as a
deletion and an addition.

The TESTING files are read from --repo. Only TESTING files are read, so --repo
can be a real checkout or a directory holding just TESTING files laid out
like one, e.g. a draft set for a repo that has none yet.

The output is a JSON list with, per PR, its pr, title, merge_commit_sha and
merged_at, then either the cli.compute result (changed_files, deleted_files,
testing_files, actions, test_runs, jobs) or "error". A summary goes to stderr.
"""

from __future__ import annotations

import argparse
import collections
import json
import shlex
import sys

from presubmit import cli
from presubmit import discover
from presubmit import jobs as jobs_lib
from presubmit import plan as plan_lib
from presubmit import source_tree

_PR_FIELDS = ("pr", "title", "merge_commit_sha", "merged_at")


def pr_changes(files: list) -> tuple:
    """Returns (changed, deleted) paths for a pr_files.py file list."""
    changed, deleted = set(), set()
    for f in files:
        changed.add(f["filename"])
        if f["status"] == "removed":
            deleted.add(f["filename"])
        if f.get("previous_filename"):
            changed.add(f["previous_filename"])
            deleted.add(f["previous_filename"])
    return sorted(changed), sorted(deleted)


def backtest(tree: source_tree.SourceTree, prs: list, **compute_args) -> list:
    """Returns one result per PR. A PR whose plan fails gets "error" instead."""
    results = []
    for pr in prs:
        result = {k: pr.get(k) for k in _PR_FIELDS}
        changed, deleted = pr_changes(pr["files"])
        try:
            result.update(cli.compute(tree, changed, deleted_files=deleted, **compute_args))
        except cli.USER_ERRORS as e:
            result["error"] = str(e)
        results.append(result)
    return results


def summary(results: list) -> str:
    errors = [r for r in results if "error" in r]
    planned = [r for r in results if "error" not in r]
    no_jobs = [r for r in planned if not r["jobs"]]
    job_counts = collections.Counter(j["name"] for r in planned for j in r["jobs"])
    lines = ["%d PRs: %d with jobs, %d with no jobs, %d errors" % (
        len(results), len(planned) - len(no_jobs), len(no_jobs), len(errors))]
    for name, n in sorted(job_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append("  %4d  %s" % (n, name))
    for r in errors:
        lines.append("  error in PR %s: %s" % (r["pr"], r["error"]))
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Plan the presubmit jobs for past PRs listed by pr_files.py.",
        allow_abbrev=False)
    parser.add_argument(
        "prs", nargs="?", default="-",
        help="pr_files.py JSON output; '-' (the default) reads stdin")
    parser.add_argument(
        "--repo", default=".",
        help="root of the tree holding the TESTING files (default: current directory)")
    parser.add_argument("--pr", type=int, action="append", help="only this PR; repeatable")
    parser.add_argument(
        "--out", default="-", help="where to write the JSON results; '-' (the default) is stdout")
    parser.add_argument("--filename", default=discover.DEFAULT_FILENAME)
    parser.add_argument("--default_machine_type", action="append", metavar="TYPE")
    parser.add_argument("--run_actions", default=shlex.join(jobs_lib.RUN_ACTIONS_COMMAND))
    parser.add_argument("--bazel", default=shlex.join(jobs_lib.BAZEL_COMMAND))
    args = parser.parse_args(argv)

    if args.prs == "-":
        prs = json.load(sys.stdin)
    else:
        with open(args.prs, encoding="utf-8") as f:
            prs = json.load(f)
    if args.pr:
        prs = [p for p in prs if p["pr"] in args.pr]
    results = backtest(
        source_tree.FsSourceTree(args.repo), prs,
        filename=args.filename,
        default_machine_types=args.default_machine_type or plan_lib.DEFAULT_MACHINE_TYPES,
        run_actions_command=shlex.split(args.run_actions),
        bazel_command=shlex.split(args.bazel))
    text = json.dumps(results, indent=2, sort_keys=True) + "\n"
    if args.out == "-":
        sys.stdout.write(text)
    else:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
    print(summary(results), file=sys.stderr)
    return 0
