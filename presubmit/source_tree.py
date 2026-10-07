"""Read-only access to a source tree, real or mocked.

All paths are relative to the root of the source tree and use "/" separators.
"""

from __future__ import annotations

import os
import posixpath
import re


class SourceTreeError(Exception):
    """A bad path, or a malformed mock tree spec."""


def normalize_path(path: str) -> str:
    """Returns path relative to the tree root, in normal form.

    A leading "/" means the tree root, not the filesystem root. Paths that
    would leave the tree (via "..") are rejected.
    """
    stripped = path.strip().lstrip("/")
    if not stripped:
        raise SourceTreeError("empty path: %r" % path)
    normalized = posixpath.normpath(stripped)
    if normalized == ".." or normalized.startswith("../"):
        raise SourceTreeError("path leaves the source tree: %r" % path)
    return normalized


class SourceTree:
    """Interface for reading files in a source tree."""

    def exists(self, path: str) -> bool:
        """Returns True if path names a file in the tree."""
        raise NotImplementedError

    def read(self, path: str) -> str:
        """Returns the text content of the file at path.

        Raises FileNotFoundError if there is no such file.
        """
        raise NotImplementedError


class FsSourceTree(SourceTree):
    """A source tree on the local filesystem."""

    def __init__(self, root: str):
        self.root = root

    def _full_path(self, path: str) -> str:
        return os.path.join(self.root, *normalize_path(path).split("/"))

    def exists(self, path: str) -> bool:
        return os.path.isfile(self._full_path(path))

    def read(self, path: str) -> str:
        with open(self._full_path(path), encoding="utf-8") as f:
            return f.read()


class MockSourceTree(SourceTree):
    """An in-memory source tree, for tests."""

    def __init__(self, files: dict):
        # Maps normalized path -> content.
        self.files = {}
        for path, content in files.items():
            self.files[normalize_path(path)] = content

    def exists(self, path: str) -> bool:
        return normalize_path(path) in self.files

    def read(self, path: str) -> str:
        normalized = normalize_path(path)
        if normalized not in self.files:
            raise FileNotFoundError(path)
        return self.files[normalized]

    def paths(self) -> list:
        """Returns all file paths, sorted."""
        return sorted(self.files)


# "path <<<TAG": the file's content follows, up to a line that is exactly TAG.
_HEREDOC_RE = re.compile(r"^(.*?)\s*<<<([A-Za-z0-9_]+)$")


def parse_mock_tree(text: str) -> MockSourceTree:
    """Builds a MockSourceTree from a spec, one file per line.

        /src/main/foo.c
        /src/main/TESTING <<<END
        presubmit { check_action: "lint" }
        END
        # Lines starting with "#", and blank lines, are ignored.
        /src/common/baz.c

    A plain path line makes an empty file. A path line ending in <<<TAG takes
    the following lines, up to a line that is exactly TAG, as the content
    (each line keeps its trailing newline).
    """
    files = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        line_number = i + 1
        i += 1
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        content = ""
        match = _HEREDOC_RE.match(stripped)
        if match:
            raw_path, tag = match.group(1), match.group(2)
            body = []
            while i < len(lines) and lines[i] != tag:
                body.append(lines[i] + "\n")
                i += 1
            if i >= len(lines):
                raise SourceTreeError(
                    "line %d: no closing %r for %s" % (line_number, tag, raw_path))
            i += 1  # Skip the closing tag.
            content = "".join(body)
        else:
            raw_path = stripped

        try:
            path = normalize_path(raw_path)
        except SourceTreeError as e:
            raise SourceTreeError("line %d: %s" % (line_number, e)) from e
        if path in files:
            raise SourceTreeError("line %d: duplicate path %s" % (line_number, path))
        files[path] = content
    return MockSourceTree(files)
