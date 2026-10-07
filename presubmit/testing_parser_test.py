import unittest

from presubmit import testing_parser

_FULL = """
include: "common/TESTING"
include: "tools/lint/TESTING"

action {
  name: "shellcheck"
  command: "shellcheck {FILES}"
  machine_type: "linux_amd64"
  machine_type: "linux_arm64"
}

test_suite {
  name: "unit"
  tests: "//pkg/..."
  tests: "//cmd/..."
  test_args: "--test_output=errors"
  platform: "//platforms:linux_x64"
}

presubmit {
  include_regex: "\\\\.sh$"
  exclude_regex: "^third_party/"
  check_action: "shellcheck"
  check_tests: "unit"
}
"""


class ParseTestingTest(unittest.TestCase):
    def test_all_fields(self):
        t = testing_parser.parse_testing(_FULL)
        self.assertEqual(list(t.include), ["common/TESTING", "tools/lint/TESTING"])

        self.assertEqual(len(t.action), 1)
        a = t.action[0]
        self.assertEqual(a.name, "shellcheck")
        self.assertEqual(a.command, "shellcheck {FILES}")
        self.assertEqual(list(a.machine_type), ["linux_amd64", "linux_arm64"])

        self.assertEqual(len(t.test_suite), 1)
        s = t.test_suite[0]
        self.assertEqual(s.name, "unit")
        self.assertEqual(list(s.tests), ["//pkg/...", "//cmd/..."])
        self.assertEqual(list(s.test_args), ["--test_output=errors"])
        self.assertEqual(list(s.platform), ["//platforms:linux_x64"])

        self.assertEqual(len(t.presubmit), 1)
        p = t.presubmit[0]
        self.assertEqual(list(p.include_regex), ["\\.sh$"])
        self.assertEqual(list(p.exclude_regex), ["^third_party/"])
        self.assertEqual(list(p.check_action), ["shellcheck"])
        self.assertEqual(list(p.check_tests), ["unit"])

    def test_empty(self):
        t = testing_parser.parse_testing("")
        self.assertEqual(len(t.include), 0)
        self.assertEqual(len(t.presubmit), 0)

    def test_comments(self):
        t = testing_parser.parse_testing('# a comment\ninclude: "x/TESTING"  # trailing\n')
        self.assertEqual(list(t.include), ["x/TESTING"])

    def test_unknown_field_error_names_path(self):
        with self.assertRaises(testing_parser.ParseError) as cm:
            testing_parser.parse_testing("no_such_field: 1", path="src/TESTING")
        self.assertIn("src/TESTING", str(cm.exception))
        self.assertIn("no_such_field", str(cm.exception))

    def test_syntax_error(self):
        with self.assertRaises(testing_parser.ParseError):
            testing_parser.parse_testing("action { name: ", path="src/TESTING")


if __name__ == "__main__":
    unittest.main()
