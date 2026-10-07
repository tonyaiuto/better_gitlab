"""Command line for computing a presubmit plan, printed as JSON.

The source of changed files is pluggable: main() takes a function that builds
a ChangedFiles from the parsed arguments. main.py wires in git diff; another
version control system or review service provides its own main.py:

    from presubmit import cli

    def make_changed_files(args):
        return MyReviewChangedFiles(os.environ["REVIEW_ID"])

    if __name__ == "__main__":
        sys.exit(cli.main(make_changed_files=make_changed_files))
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from presubmit import changed_files as changed_files_lib
from presubmit import discover
from presubmit import loader
from presubmit import plan as plan_lib
from presubmit import selection
from presubmit import source_tree

DEFAULT_REF = "origin/main...HEAD"


def compute(
        tree: source_tree.SourceTree,
        changed_files: list,
        filename: str = discover.DEFAULT_FILENAME,
        default_machine_types: list = plan_lib.DEFAULT_MACHINE_TYPES) -> dict:
    """Runs the whole pipeline and returns the result as a JSON-ready dict."""
    testing_files = discover.find_testing_files(tree, changed_files, filename)
    loaded = loader.load(tree, testing_files)
    selections = selection.select(loaded, changed_files)
    plan = plan_lib.build_plan(loaded, selections, default_machine_types)
    return {
        "changed_files": list(changed_files),
        "testing_files": testing_files,
        "actions": [asdict(a) for a in plan.actions],
        "test_runs": [asdict(t) for t in plan.test_runs],
    }


def git_changed_files(args) -> changed_files_lib.ChangedFiles:
    return changed_files_lib.GitDiffChangedFiles(args.ref, repo_root=args.repo)


# Errors that mean bad input rather than a bug.
_USER_ERRORS = (
    changed_files_lib.ChangedFilesError,
    loader.LoadError,
    plan_lib.PlanError,
    selection.SelectError,
    source_tree.SourceTreeError,
    ValueError,
)


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Work out which actions and tests to run for the files "
                    "changed in a PR, from the TESTING files in the source tree.",
        allow_abbrev=False)
    parser.add_argument(
        "--repo", default=".",
        help="root of the source tree (default: current directory)")
    parser.add_argument(
        "--ref", default=DEFAULT_REF,
        help="git ref to diff against, passed to `git diff --name-only` "
             "(default: %(default)s)")
    parser.add_argument(
        "--file", action="append", dest="files", metavar="PATH",
        help="use this changed file instead of asking for the changed files; repeatable")
    parser.add_argument(
        "--filename", default=discover.DEFAULT_FILENAME,
        help="name of the files declaring actions (default: %(default)s)")
    parser.add_argument(
        "--default_machine_type", action="append", metavar="TYPE",
        help="machine type for actions that name none; repeatable "
             "(default: %s)" % ", ".join(plan_lib.DEFAULT_MACHINE_TYPES))
    return parser


def main(argv=None, make_changed_files=git_changed_files, add_arguments=None) -> int:
    """Runs the command line. Returns the exit code.

    make_changed_files(args) returns the ChangedFiles to use when --file is not
    given. add_arguments(parser), if given, can add flags for it.
    """
    parser = make_parser()
    if add_arguments:
        add_arguments(parser)
    args = parser.parse_args(argv)
    try:
        if args.files:
            changed = changed_files_lib.FixedChangedFiles(args.files)
        else:
            changed = make_changed_files(args)
        result = compute(
            source_tree.FsSourceTree(args.repo),
            changed.get(),
            filename=args.filename,
            default_machine_types=args.default_machine_type or plan_lib.DEFAULT_MACHINE_TYPES)
    except _USER_ERRORS as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0
