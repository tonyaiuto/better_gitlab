import unittest

from run_actions import action as action_lib
from run_actions.action import Action, ActionResult


class ParseActionTest(unittest.TestCase):
    def test_named(self):
        a = action_lib.parse_action("lint='shellcheck -x foo.sh'", 1000)
        self.assertEqual(a, Action(id=1000, name="lint", command="'shellcheck -x foo.sh'"))

    def test_named_shell_unquoted(self):
        # As the shell delivers name='cmd args': quotes are already removed.
        a = action_lib.parse_action("lint=shellcheck -x foo.sh", 1000)
        self.assertEqual(a.name, "lint")
        self.assertEqual(a.command, "shellcheck -x foo.sh")

    def test_named_with_dots_and_dashes(self):
        a = action_lib.parse_action("lint.go-vet=go vet ./...", 1)
        self.assertEqual(a.name, "lint.go-vet")
        self.assertEqual(a.command, "go vet ./...")

    def test_named_multiline_command(self):
        a = action_lib.parse_action("x=echo a\necho b", 1)
        self.assertEqual(a.name, "x")
        self.assertEqual(a.command, "echo a\necho b")

    def test_unnamed(self):
        a = action_lib.parse_action("ls -l /", 1001)
        self.assertEqual(a, Action(id=1001, name="ls -l /", command="ls -l /"))

    def test_unnamed_equals_later(self):
        a = action_lib.parse_action("git config --get a=b", 1)
        self.assertEqual(a.name, "git config --get a=b")
        self.assertEqual(a.command, "git config --get a=b")

    def test_env_assignment_is_read_as_name(self):
        # Documented ambiguity.
        a = action_lib.parse_action("FOO=1 make", 1)
        self.assertEqual(a.name, "FOO")
        self.assertEqual(a.command, "1 make")

    def test_ids(self):
        actions = action_lib.parse_actions(["a=x", "y", "c=z"])
        self.assertEqual([a.id for a in actions], [1000, 1001, 1002])
        self.assertEqual([a.name for a in actions], ["a", "y", "c"])


class VariablesTest(unittest.TestCase):
    def test_passed(self):
        r = ActionResult(Action(1000, "n", "c"), 0, b"", b"")
        self.assertEqual(
            action_lib.variables(r),
            {
                "ACTION_NAME": "n",
                "ACTION_ID": "1000",
                "ESC": "\x1b",
                "EXIT_CODE": "0",
                "PASSED": "true",
                "FAILED": "false",
            },
        )

    def test_failed(self):
        r = ActionResult(Action(1003, "n", "c"), 3, b"", b"")
        v = action_lib.variables(r)
        self.assertEqual(v["EXIT_CODE"], "3")
        self.assertEqual(v["PASSED"], "false")
        self.assertEqual(v["FAILED"], "true")


if __name__ == "__main__":
    unittest.main()
