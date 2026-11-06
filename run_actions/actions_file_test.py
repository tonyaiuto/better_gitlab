import os
import shutil
import tempfile
import unittest

from run_actions import actions_file
from run_actions.action import Action

_EXAMPLE = """
action {
  name: "lint"
  script: "echo lint"
}
action {
  name: "flaky"
  script: "echo one\\n"
          "echo two"
  ignore_error: true
}
"""


class ActionsFileTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write(self, text):
        path = os.path.join(self.tmpdir, "actions.textproto")
        with open(path, "w") as f:
            f.write(text)
        return path

    def test_load(self):
        actions = actions_file.load(self._write(_EXAMPLE), 1000)
        self.assertEqual(
            actions,
            [
                Action(id=1000, name="lint", command="echo lint"),
                Action(id=1001, name="flaky", command="echo one\necho two", ignore_error=True),
            ],
        )

    def test_first_id(self):
        actions = actions_file.load(self._write(_EXAMPLE), 1005)
        self.assertEqual([a.id for a in actions], [1005, 1006])

    def test_empty_file(self):
        self.assertEqual(actions_file.load(self._write(""), 1000), [])

    def test_bad_syntax_names_path(self):
        path = self._write("action { nme: 'x' }")
        with self.assertRaisesRegex(actions_file.ParseError, "actions.textproto"):
            actions_file.load(path, 1000)

    def test_missing_name(self):
        with self.assertRaisesRegex(actions_file.ParseError, "action #1 has no name"):
            actions_file.load(self._write("action { script: 'true' }"), 1000)

    def test_missing_script(self):
        with self.assertRaisesRegex(actions_file.ParseError, "'x' has no script"):
            actions_file.load(self._write("action { name: 'x' }"), 1000)

    def test_missing_file(self):
        with self.assertRaisesRegex(actions_file.ParseError, "nope"):
            actions_file.load(os.path.join(self.tmpdir, "nope"), 1000)


if __name__ == "__main__":
    unittest.main()
