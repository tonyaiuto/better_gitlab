"""Loading TESTING files: parsing, includes, and the global definitions.

Each TESTING file found by discover.find_testing_files is a "scope": its
presubmit blocks apply to changed files in its directory and below.

An include brings in everything from the included file, transitively: its
Action and TestSuite definitions, and its presubmit blocks, which then apply
within the scope of the file that was found (not the directory of the included
file).

Action and TestSuite names are global across all loaded files. Defining a name
twice is an error unless both definitions are identical.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from presubmit import source_tree
from presubmit import testing_parser
from presubmit import testing_pb2


class LoadError(Exception):
    """TESTING files could not be loaded, or are inconsistent."""


@dataclass
class ScopedPresubmit:
    """A presubmit block, with the scope it applies in."""

    # The TESTING file whose directory bounds the files this block sees.
    scope: str
    # The file the block is written in: scope itself, or a file it includes.
    source: str
    presubmit: testing_pb2.Presubmit


@dataclass
class Loaded:
    """Everything read from a set of TESTING files."""

    # name -> testing_pb2.Action
    actions: dict = field(default_factory=dict)
    # name -> testing_pb2.TestSuite
    test_suites: dict = field(default_factory=dict)
    # In scope order (as given to load), then in include order within a scope.
    presubmits: list = field(default_factory=list)


class _Loader:
    def __init__(self, tree: source_tree.SourceTree):
        self.tree = tree
        # path -> parsed Testing message.
        self.parsed = {}
        # name -> path of the file that defined it.
        self.action_sources = {}
        self.test_suite_sources = {}
        self.loaded = Loaded()

    def parse(self, path: str, included_from: str) -> testing_pb2.Testing:
        if path not in self.parsed:
            if not self.tree.exists(path):
                if included_from:
                    raise LoadError("%s: included file not found: %s" % (included_from, path))
                raise LoadError("file not found: %s" % path)
            try:
                self.parsed[path] = testing_parser.parse_testing(self.tree.read(path), path)
            except testing_parser.ParseError as e:
                raise LoadError(str(e)) from e
            self.add_definitions(path, self.parsed[path])
        return self.parsed[path]

    def add_definitions(self, path: str, testing: testing_pb2.Testing):
        for action in testing.action:
            _add_definition(
                "action", action, path, self.loaded.actions, self.action_sources)
        for suite in testing.test_suite:
            _add_definition(
                "test_suite", suite, path, self.loaded.test_suites, self.test_suite_sources)

    def load_scope(self, scope: str):
        # Each file contributes its presubmit blocks to a scope at most once,
        # even if it is included along several paths.
        visited = set()
        self.visit(scope, scope, [], visited)

    def visit(self, scope: str, path: str, chain: list, visited: set):
        if path in chain:
            raise LoadError("include cycle: %s" % " -> ".join(chain + [path]))
        if path in visited:
            return
        visited.add(path)
        testing = self.parse(path, chain[-1] if chain else "")
        for presubmit in testing.presubmit:
            self.loaded.presubmits.append(ScopedPresubmit(scope, path, presubmit))
        for include in testing.include:
            try:
                included = source_tree.normalize_path(include)
            except source_tree.SourceTreeError as e:
                raise LoadError("%s: bad include: %s" % (path, e)) from e
            self.visit(scope, included, chain + [path], visited)


def _add_definition(kind: str, message, path: str, definitions: dict, sources: dict):
    name = message.name
    if not name:
        raise LoadError("%s: %s with no name" % (path, kind))
    if name in definitions:
        if definitions[name] != message:
            raise LoadError(
                "%s: %s %r is already defined differently in %s"
                % (path, kind, name, sources[name]))
        return
    definitions[name] = message
    sources[name] = path


def _validate(loaded: Loaded, action_sources: dict):
    errors = []
    for name, action in sorted(loaded.actions.items()):
        if not action.command:
            errors.append("%s: action %r has no command" % (action_sources[name], name))
    for scoped in loaded.presubmits:
        for name in scoped.presubmit.check_action:
            if name not in loaded.actions:
                errors.append("%s: check_action names unknown action %r" % (scoped.source, name))
        for name in scoped.presubmit.check_tests:
            if name not in loaded.test_suites:
                errors.append(
                    "%s: check_tests names unknown test_suite %r" % (scoped.source, name))
    if errors:
        # The same block can be loaded in several scopes; report each error once.
        raise LoadError("\n".join(sorted(set(errors))))


def load(tree: source_tree.SourceTree, testing_paths: list) -> Loaded:
    """Loads the TESTING files at testing_paths, each as its own scope."""
    loader = _Loader(tree)
    for path in testing_paths:
        loader.load_scope(source_tree.normalize_path(path))
    _validate(loader.loaded, loader.action_sources)
    return loader.loaded
