import unittest

from presubmit import loader
from presubmit import source_tree
from presubmit.loader import LoadError


def _load(spec, paths):
    return loader.load(source_tree.parse_mock_tree(spec), paths)


def _presubmits(loaded):
    """(scope, source, check_actions) for each loaded presubmit block."""
    return [
        (p.scope, p.source, list(p.presubmit.check_action) + list(p.presubmit.check_tests))
        for p in loaded.presubmits
    ]


_COMMON = """
/common/TESTING <<<END
action { name: "lint" command: "lint {FILES}" }
test_suite { name: "unit" tests: "//..." }
presubmit { check_action: "lint" }
END
"""


class LoadTest(unittest.TestCase):
    def test_single_file(self):
        loaded = _load("""
/a/TESTING <<<END
action { name: "fmt" command: "fmt {EACH_FILE}" machine_type: "linux" }
test_suite { name: "unit" tests: "//a/..." }
presubmit { check_action: "fmt" check_tests: "unit" }
END
""", ["a/TESTING"])
        self.assertEqual(sorted(loaded.actions), ["fmt"])
        self.assertEqual(loaded.actions["fmt"].command, "fmt {EACH_FILE}")
        self.assertEqual(sorted(loaded.test_suites), ["unit"])
        self.assertEqual(_presubmits(loaded), [("a/TESTING", "a/TESTING", ["fmt", "unit"])])

    def test_names_are_global_across_scopes(self):
        loaded = _load("""
/TESTING <<<END
action { name: "lint" command: "lint" }
END
/a/TESTING <<<END
presubmit { check_action: "lint" }
END
""", ["TESTING", "a/TESTING"])
        self.assertEqual(_presubmits(loaded), [("a/TESTING", "a/TESTING", ["lint"])])

    def test_include_brings_definitions_and_presubmits_into_scope(self):
        loaded = _load(_COMMON + """
/a/TESTING <<<END
include: "common/TESTING"
presubmit { check_tests: "unit" }
END
""", ["a/TESTING"])
        self.assertEqual(sorted(loaded.actions), ["lint"])
        self.assertEqual(sorted(loaded.test_suites), ["unit"])
        self.assertEqual(_presubmits(loaded), [
            ("a/TESTING", "a/TESTING", ["unit"]),
            ("a/TESTING", "common/TESTING", ["lint"]),
        ])

    def test_include_path_leading_slash(self):
        loaded = _load(_COMMON + '/a/TESTING <<<END\ninclude: "/common/TESTING"\nEND\n',
                       ["a/TESTING"])
        self.assertEqual(_presubmits(loaded), [("a/TESTING", "common/TESTING", ["lint"])])

    def test_shared_include_applies_in_each_scope(self):
        loaded = _load(_COMMON + """
/a/TESTING <<<END
include: "common/TESTING"
END
/b/TESTING <<<END
include: "common/TESTING"
END
""", ["a/TESTING", "b/TESTING"])
        self.assertEqual(_presubmits(loaded), [
            ("a/TESTING", "common/TESTING", ["lint"]),
            ("b/TESTING", "common/TESTING", ["lint"]),
        ])

    def test_transitive_include(self):
        loaded = _load(_COMMON + """
/mid/TESTING <<<END
include: "common/TESTING"
presubmit { check_tests: "unit" }
END
/a/TESTING <<<END
include: "mid/TESTING"
END
""", ["a/TESTING"])
        self.assertEqual(_presubmits(loaded), [
            ("a/TESTING", "mid/TESTING", ["unit"]),
            ("a/TESTING", "common/TESTING", ["lint"]),
        ])

    def test_diamond_include_loads_once_per_scope(self):
        loaded = _load(_COMMON + """
/x/TESTING <<<END
include: "common/TESTING"
END
/y/TESTING <<<END
include: "common/TESTING"
END
/a/TESTING <<<END
include: "x/TESTING"
include: "y/TESTING"
END
""", ["a/TESTING"])
        self.assertEqual(_presubmits(loaded), [("a/TESTING", "common/TESTING", ["lint"])])

    def test_include_cycle(self):
        with self.assertRaises(LoadError) as cm:
            _load("""
/a/TESTING <<<END
include: "b/TESTING"
END
/b/TESTING <<<END
include: "a/TESTING"
END
""", ["a/TESTING"])
        self.assertIn("include cycle: a/TESTING -> b/TESTING -> a/TESTING", str(cm.exception))

    def test_self_include(self):
        with self.assertRaises(LoadError) as cm:
            _load('/a/TESTING <<<END\ninclude: "a/TESTING"\nEND\n', ["a/TESTING"])
        self.assertIn("include cycle", str(cm.exception))

    def test_missing_include(self):
        with self.assertRaises(LoadError) as cm:
            _load('/a/TESTING <<<END\ninclude: "nope/TESTING"\nEND\n', ["a/TESTING"])
        self.assertIn("a/TESTING: included file not found: nope/TESTING", str(cm.exception))

    def test_bad_include_path(self):
        with self.assertRaises(LoadError) as cm:
            _load('/a/TESTING <<<END\ninclude: "../x"\nEND\n', ["a/TESTING"])
        self.assertIn("a/TESTING: bad include", str(cm.exception))

    def test_parse_error_names_file(self):
        with self.assertRaises(LoadError) as cm:
            _load("/a/TESTING <<<END\nbogus: 1\nEND\n", ["a/TESTING"])
        self.assertIn("a/TESTING", str(cm.exception))

    def test_identical_redefinition_is_fine(self):
        loaded = _load("""
/a/TESTING <<<END
action { name: "lint" command: "lint" }
END
/b/TESTING <<<END
action { name: "lint" command: "lint" }
END
""", ["a/TESTING", "b/TESTING"])
        self.assertEqual(sorted(loaded.actions), ["lint"])

    def test_conflicting_redefinition(self):
        with self.assertRaises(LoadError) as cm:
            _load("""
/a/TESTING <<<END
action { name: "lint" command: "lint" }
END
/b/TESTING <<<END
action { name: "lint" command: "lint --strict" }
END
""", ["a/TESTING", "b/TESTING"])
        self.assertIn(
            "b/TESTING: action 'lint' is already defined differently in a/TESTING",
            str(cm.exception))

    def test_conflicting_test_suite(self):
        with self.assertRaises(LoadError) as cm:
            _load("""
/a/TESTING <<<END
test_suite { name: "unit" tests: "//a/..." }
test_suite { name: "unit" tests: "//b/..." }
END
""", ["a/TESTING"])
        self.assertIn("test_suite 'unit'", str(cm.exception))

    def test_action_needs_name(self):
        with self.assertRaises(LoadError) as cm:
            _load('/a/TESTING <<<END\naction { command: "x" }\nEND\n', ["a/TESTING"])
        self.assertIn("a/TESTING: action with no name", str(cm.exception))

    def test_test_suite_needs_name(self):
        with self.assertRaises(LoadError) as cm:
            _load('/a/TESTING <<<END\ntest_suite { tests: "//..." }\nEND\n', ["a/TESTING"])
        self.assertIn("a/TESTING: test_suite with no name", str(cm.exception))

    def test_action_needs_command(self):
        with self.assertRaises(LoadError) as cm:
            _load('/a/TESTING <<<END\naction { name: "x" }\nEND\n', ["a/TESTING"])
        self.assertIn("a/TESTING: action 'x' has no command", str(cm.exception))

    def test_unknown_names_all_reported(self):
        with self.assertRaises(LoadError) as cm:
            _load("""
/a/TESTING <<<END
presubmit { check_action: "nope" check_tests: "nada" }
END
""", ["a/TESTING"])
        self.assertIn("a/TESTING: check_action names unknown action 'nope'", str(cm.exception))
        self.assertIn(
            "a/TESTING: check_tests names unknown test_suite 'nada'", str(cm.exception))

    def test_name_must_be_loaded_to_be_known(self):
        # Defined in a file that is neither in scope nor included.
        with self.assertRaises(LoadError):
            _load(_COMMON + '/a/TESTING <<<END\npresubmit { check_action: "lint" }\nEND\n',
                  ["a/TESTING"])

    def test_no_files(self):
        loaded = _load("", [])
        self.assertEqual(loaded.actions, {})
        self.assertEqual(loaded.presubmits, [])


if __name__ == "__main__":
    unittest.main()
