import contextlib
import io
import json
import os
import tempfile
import unittest

from presubmit import changed_files
from presubmit import cli


class MainTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = self.dir.name
        os.makedirs(os.path.join(self.root, "a"))
        with open(os.path.join(self.root, "a", "TESTING"), "w") as f:
            f.write('action { name: "lint" command: "lint {FILES}" }\n'
                    'presubmit { check_action: "lint" }\n')

    def tearDown(self):
        self.dir.cleanup()

    def run_main(self, argv, **kwargs):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(argv, **kwargs)
        return code, out.getvalue(), err.getvalue()

    def test_files_flag(self):
        code, out, _ = self.run_main(["--repo", self.root, "--file", "a/x.c", "--file", "b.c"])
        self.assertEqual(code, 0)
        result = json.loads(out)
        self.assertEqual(result["testing_files"], ["a/TESTING"])
        self.assertEqual(result["actions"][0]["commands"], ["lint a/x.c"])

    def test_default_machine_type_flag(self):
        code, out, _ = self.run_main([
            "--repo", self.root, "--file", "a/x.c",
            "--default_machine_type", "linux", "--default_machine_type", "mac"])
        self.assertEqual(code, 0)
        self.assertEqual([a["machine_type"] for a in json.loads(out)["actions"]],
                         ["linux", "mac"])

    def test_filename_flag(self):
        code, out, _ = self.run_main(
            ["--repo", self.root, "--file", "a/x.c", "--filename", "METADATA"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["testing_files"], [])

    def test_pluggable_changed_files(self):
        seen = {}

        def add_arguments(parser):
            parser.add_argument("--review")

        def make(args):
            seen["review"] = args.review
            return changed_files.FixedChangedFiles(["a/from_review.c"])

        code, out, _ = self.run_main(
            ["--repo", self.root, "--review", "123"],
            make_changed_files=make, add_arguments=add_arguments)
        self.assertEqual(code, 0)
        self.assertEqual(seen, {"review": "123"})
        self.assertEqual(json.loads(out)["changed_files"], ["a/from_review.c"])

    def test_error_exit(self):
        with open(os.path.join(self.root, "a", "TESTING"), "w") as f:
            f.write("bogus: 1\n")
        code, out, err = self.run_main(["--repo", self.root, "--file", "a/x.c"])
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("error: a/TESTING", err)


if __name__ == "__main__":
    unittest.main()
