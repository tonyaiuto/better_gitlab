"""Applying presubmit blocks to the changed files.

(Named selection, not select, so it can't shadow the standard library's
select module when this directory is first on sys.path.)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from presubmit import discover
from presubmit import loader


class SelectError(Exception):
    """A presubmit block could not be applied, e.g. a bad regex."""


@dataclass
class Selection:
    """A presubmit block that matched some changed files."""

    scope: str
    source: str
    # Names, as written in the block.
    actions: list
    test_suites: list
    # The changed files that made it through the block's regexes, sorted.
    files: list


def _compile(patterns, source: str, field_name: str) -> list:
    compiled = []
    for pattern in patterns:
        try:
            compiled.append(re.compile(pattern))
        except re.error as e:
            raise SelectError("%s: bad %s %r: %s" % (source, field_name, pattern, e)) from e
    return compiled


def matching_files(scoped: loader.ScopedPresubmit, changed_files: list) -> list:
    """Returns the changed files that a presubmit block applies to.

    Starts with the files in the block's scope. If the block has include_regex
    entries, keeps the files any of them matches (re.search on the
    repo-relative path). Then drops the files any exclude_regex matches.
    """
    presubmit = scoped.presubmit
    includes = _compile(presubmit.include_regex, scoped.source, "include_regex")
    excludes = _compile(presubmit.exclude_regex, scoped.source, "exclude_regex")
    files = discover.files_in_scope(scoped.scope, changed_files)
    if includes:
        files = [f for f in files if any(r.search(f) for r in includes)]
    files = [f for f in files if not any(r.search(f) for r in excludes)]
    return sorted(files)


def select(loaded: loader.Loaded, changed_files: list) -> list:
    """Returns a Selection for each presubmit block with matching files.

    Blocks with no matching files, or nothing to run, are skipped. The order
    follows loaded.presubmits.
    """
    selections = []
    for scoped in loaded.presubmits:
        presubmit = scoped.presubmit
        if not presubmit.check_action and not presubmit.check_tests:
            continue
        files = matching_files(scoped, changed_files)
        if not files:
            continue
        selections.append(Selection(
            scope=scoped.scope,
            source=scoped.source,
            actions=list(presubmit.check_action),
            test_suites=list(presubmit.check_tests),
            files=files))
    return selections
