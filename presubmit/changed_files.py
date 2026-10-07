"""Getting the set of files changed in a PR.

ChangedFiles is the interface. GitDiffChangedFiles is the default
implementation; other version control systems or code review services can
provide their own and build a binary around it (see cli.py).
"""

from __future__ import annotations

import subprocess

from presubmit import source_tree


class ChangedFilesError(Exception):
    """The changed files could not be determined."""


class ChangedFiles:
    """Interface for getting the files changed in a PR."""

    def get(self) -> list:
        """Returns the changed paths, relative to the repo root, sorted and unique."""
        raise NotImplementedError


def _clean(paths) -> list:
    return sorted(set(source_tree.normalize_path(p) for p in paths))


class FixedChangedFiles(ChangedFiles):
    """A fixed list of paths, for tests."""

    def __init__(self, paths):
        self.paths = _clean(paths)

    def get(self) -> list:
        return list(self.paths)


class GitDiffChangedFiles(ChangedFiles):
    """Runs `git diff --name-only <ref>` in a git checkout.

    ref is passed through to git as is, so "origin/main" (the working tree
    against origin/main) and "origin/main...HEAD" (HEAD against its merge base
    with origin/main) both work.

    Deleted files are included. Renames are reported as both the old and the
    new path, so the TESTING files of both locations apply.
    """

    def __init__(self, ref: str, repo_root: str = ".", git: str = "git"):
        self.ref = ref
        self.repo_root = repo_root
        self.git = git

    def get(self) -> list:
        command = [
            self.git, "-C", self.repo_root,
            "diff", "--name-only", "--no-renames", "-z", self.ref, "--",
        ]
        try:
            result = subprocess.run(command, capture_output=True)
        except OSError as e:
            raise ChangedFilesError("could not run %s: %s" % (self.git, e)) from e
        if result.returncode != 0:
            raise ChangedFilesError(
                "%s failed (exit %d): %s" % (
                    " ".join(command), result.returncode,
                    result.stderr.decode("utf-8", "replace").strip()))
        # -z: paths are NUL-terminated and not quoted.
        paths = result.stdout.decode("utf-8").split("\0")
        return _clean(p for p in paths if p)
