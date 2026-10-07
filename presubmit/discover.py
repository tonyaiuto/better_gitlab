"""Finding the TESTING files that apply to a set of changed files.

A TESTING file applies to every file in its directory and below, so the files
that apply to a changed file are the TESTING files in each of its ancestor
directories, up to and including the root.
"""

from __future__ import annotations

import posixpath

from presubmit import source_tree

DEFAULT_FILENAME = "TESTING"


def ancestor_dirs(path: str) -> list:
    """Returns the directories containing path, deepest first, ending with "" (the root)."""
    result = []
    directory = posixpath.dirname(path)
    while directory:
        result.append(directory)
        directory = posixpath.dirname(directory)
    result.append("")
    return result


def depth(path: str) -> int:
    """The number of directories above path: 0 for a file at the root."""
    return path.count("/")


def find_testing_files(
        tree: source_tree.SourceTree,
        changed_files: list,
        filename: str = DEFAULT_FILENAME) -> list:
    """Returns the paths of the files named filename that apply to changed_files.

    The result is sorted root first (by depth, then by path).
    """
    if not filename or "/" in filename:
        raise ValueError("filename must be a plain file name: %r" % filename)
    dirs = set()
    for path in changed_files:
        dirs.update(ancestor_dirs(source_tree.normalize_path(path)))
    found = []
    for directory in dirs:
        candidate = posixpath.join(directory, filename)
        if tree.exists(candidate):
            found.append(candidate)
    return sorted(found, key=lambda p: (depth(p), p))


def in_scope(testing_path: str, path: str) -> bool:
    """Returns True if the TESTING file at testing_path applies to path."""
    directory = posixpath.dirname(testing_path)
    return directory == "" or path.startswith(directory + "/")


def files_in_scope(testing_path: str, changed_files: list) -> list:
    """Returns the changed files that the TESTING file at testing_path applies to."""
    return [p for p in changed_files if in_scope(testing_path, p)]
