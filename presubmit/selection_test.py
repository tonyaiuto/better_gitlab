import unittest

from presubmit import discover
from presubmit import loader
from presubmit import selection
from presubmit import source_tree
from presubmit.selection import SelectError

_DEFS = """
/TESTING <<<END
action { name: "lint" command: "lint {FILES}" }
action { name: "shellcheck" command: "shellcheck {FILES}" }
test_suite { name: "unit" tests: "//..." }
END
"""


def _select(spec, changed):
    tree = source_tree.parse_mock_tree(_DEFS + spec)
    loaded = loader.load(tree, discover.find_testing_files(tree, changed))
    return selection.select(loaded, changed)


def _summary(selections):
    return [(s.source, s.actions + s.test_suites, s.files) for s in selections]


class SelectTest(unittest.TestCase):
    def test_no_regex_means_all_files_in_scope(self):
        self.assertEqual(
            _summary(_select('/a/TESTING <<<END\npresubmit { check_action: "lint" }\nEND\n',
                             ["a/x.c", "a/b/y.c", "b/z.c"])),
            [("a/TESTING", ["lint"], ["a/b/y.c", "a/x.c"])])

    def test_include_regex(self):
        self.assertEqual(
            _summary(_select("""
/a/TESTING <<<END
presubmit { include_regex: "\\\\.sh$" check_action: "shellcheck" }
END
""", ["a/run.sh", "a/x.c", "a/b/test.sh"])),
            [("a/TESTING", ["shellcheck"], ["a/b/test.sh", "a/run.sh"])])

    def test_any_include_regex_matches(self):
        self.assertEqual(
            _summary(_select("""
/a/TESTING <<<END
presubmit { include_regex: "\\\\.c$" include_regex: "\\\\.h$" check_action: "lint" }
END
""", ["a/x.c", "a/x.h", "a/x.py"])),
            [("a/TESTING", ["lint"], ["a/x.c", "a/x.h"])])

    def test_regex_searches_repo_relative_path(self):
        # re.search, so unanchored patterns match anywhere in the path, and
        # ^ anchors at the repo root, not at the TESTING file's directory.
        self.assertEqual(
            _summary(_select("""
/a/TESTING <<<END
presubmit { include_regex: "^a/gen/" check_action: "lint" }
presubmit { include_regex: "^gen/" check_tests: "unit" }
END
""", ["a/gen/x.c", "a/y.c"])),
            [("a/TESTING", ["lint"], ["a/gen/x.c"])])

    def test_exclude_applies_after_include(self):
        self.assertEqual(
            _summary(_select("""
/a/TESTING <<<END
presubmit {
  include_regex: "\\\\.c$"
  exclude_regex: "_test\\\\.c$"
  exclude_regex: "/third_party/"
  check_action: "lint"
}
END
""", ["a/x.c", "a/x_test.c", "a/third_party/z.c", "a/y.h"])),
            [("a/TESTING", ["lint"], ["a/x.c"])])

    def test_exclude_without_include(self):
        self.assertEqual(
            _summary(_select("""
/a/TESTING <<<END
presubmit { exclude_regex: "\\\\.md$" check_action: "lint" }
END
""", ["a/x.c", "a/README.md"])),
            [("a/TESTING", ["lint"], ["a/x.c"])])

    def test_everything_excluded_skips_block(self):
        self.assertEqual(
            _select("""
/a/TESTING <<<END
presubmit { exclude_regex: "." check_action: "lint" }
END
""", ["a/x.c"]),
            [])

    def test_no_match_skips_block(self):
        self.assertEqual(
            _select("""
/a/TESTING <<<END
presubmit { include_regex: "\\\\.go$" check_action: "lint" }
END
""", ["a/x.c"]),
            [])

    def test_block_with_nothing_to_run_skipped(self):
        self.assertEqual(_select("/a/TESTING <<<END\npresubmit { }\nEND\n", ["a/x.c"]), [])

    def test_included_block_uses_including_scope(self):
        self.assertEqual(
            _summary(_select("""
/common/TESTING <<<END
presubmit { include_regex: "\\\\.sh$" check_action: "shellcheck" }
END
/a/TESTING <<<END
include: "common/TESTING"
END
""", ["a/run.sh", "common/x.sh", "b/y.sh"])),
            [
                # Included by a/TESTING: a/'s scope, not common/'s.
                ("common/TESTING", ["shellcheck"], ["a/run.sh"]),
                # common/TESTING found for common/x.sh: its own scope.
                ("common/TESTING", ["shellcheck"], ["common/x.sh"]),
            ])
        self.assertEqual(
            [s.scope for s in _select("""
/common/TESTING <<<END
presubmit { include_regex: "\\\\.sh$" check_action: "shellcheck" }
END
/a/TESTING <<<END
include: "common/TESTING"
END
""", ["a/run.sh", "common/x.sh", "b/y.sh"])],
            ["a/TESTING", "common/TESTING"])

    def test_root_and_nested_scopes(self):
        self.assertEqual(
            _summary(_select("""
/a/TESTING <<<END
presubmit { check_tests: "unit" }
END
/a/b/TESTING <<<END
presubmit { check_action: "lint" }
END
""", ["a/b/x.c", "a/y.c"])),
            [
                ("a/TESTING", ["unit"], ["a/b/x.c", "a/y.c"]),
                ("a/b/TESTING", ["lint"], ["a/b/x.c"]),
            ])

    def test_bad_regex(self):
        with self.assertRaises(SelectError) as cm:
            _select('/a/TESTING <<<END\npresubmit { include_regex: "(" check_action: "lint" }\nEND\n',
                    ["a/x.c"])
        self.assertIn("a/TESTING: bad include_regex '('", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
