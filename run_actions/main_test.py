import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

from run_actions import main as main_lib


class _FakeStdout:
    """Stands in for sys.stdout, with a binary .buffer."""

    def __init__(self):
        self.buffer = io.BytesIO()

    def write(self, s):
        self.buffer.write(s.encode("utf-8"))

    def flush(self):
        pass


def _run(argv):
    fake = _FakeStdout()
    old = sys.stdout
    sys.stdout = fake
    try:
        code = main_lib.main(argv)
    finally:
        sys.stdout = old
    return code, fake.buffer.getvalue().decode("utf-8")


class ParseArgsTest(unittest.TestCase):
    def test_defaults(self):
        args = main_lib.parse_args(["a"])
        self.assertTrue(args.show_errors_last)
        self.assertFalse(args.serial)
        self.assertEqual(args.actions, ["a"])

    def test_show_errors_last_variants(self):
        cases = [
            (["--show_errors_last", "a"], True),
            (["--show_errors_last=true", "a"], True),
            (["--show_errors_last=false", "a"], False),
            (["--show_errors_last=False", "a"], False),
            (["--noshow_errors_last", "a"], False),
            (["a", "--noshow_errors_last"], False),
        ]
        for argv, expected in cases:
            args = main_lib.parse_args(argv)
            self.assertEqual(args.show_errors_last, expected, argv)
            self.assertEqual(args.actions, ["a"], argv)

    def test_bare_flag_does_not_consume_action(self):
        args = main_lib.parse_args(["--show_errors_last", "false"])
        self.assertTrue(args.show_errors_last)
        self.assertEqual(args.actions, ["false"])

    def test_serial_variants(self):
        self.assertTrue(main_lib.parse_args(["--serial", "a"]).serial)
        self.assertTrue(main_lib.parse_args(["--serial=true", "a"]).serial)
        self.assertFalse(main_lib.parse_args(["--noserial", "a"]).serial)

    def test_interleaved(self):
        args = main_lib.parse_args(["a", "--serial", "b"])
        self.assertTrue(args.serial)
        self.assertEqual(args.actions, ["a", "b"])

    def test_double_dash(self):
        args = main_lib.parse_args(["--", "--serial"])
        self.assertFalse(args.serial)
        self.assertEqual(args.actions, ["--serial"])

    def test_bad_bool(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                main_lib.parse_args(["--show_errors_last=maybe", "a"])
        self.assertEqual(cm.exception.code, 2)

    def test_no_actions(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                main_lib.parse_args([])
        self.assertEqual(cm.exception.code, 2)


class MainTest(unittest.TestCase):
    def test_all_pass(self):
        code, out = _run(["a=echo a", "b=echo b"])
        self.assertEqual(code, 0)
        self.assertLess(out.index("##### a\n"), out.index("##### b\n"))

    def test_failure_exit_code_and_errors_last(self):
        code, out = _run(["bad=exit 3", "ok=echo ok"])
        self.assertEqual(code, 1)
        self.assertLess(out.index("##### ok\n"), out.index("##### bad\n"))
        self.assertRegex(out, r"section_start:\d+:bad\[collapsed=false\]")
        self.assertRegex(out, r"section_start:\d+:ok\[collapsed=true\]")

    def test_command_line_order(self):
        code, out = _run(["--show_errors_last=false", "bad=exit 3", "ok=echo ok"])
        self.assertEqual(code, 1)
        self.assertLess(out.index("##### bad\n"), out.index("##### ok\n"))

    def test_serial_failure(self):
        code, out = _run(["--serial", "bad=exit 3", "ok=echo ok"])
        self.assertEqual(code, 1)
        self.assertRegex(out, "ok\n\x1b\\[0Ksection_end:\\d+:ok\r\x1b\\[0K\n")

    def test_junit_xml(self):
        tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmpdir)
        path = os.path.join(tmpdir, "junit.xml")
        code, out = _run(["--junit_xml=" + path, "bad=echo oops >&2; exit 3", "ok=echo ok"])
        self.assertEqual(code, 1)
        # The log shows errors last; the report keeps command line order.
        self.assertLess(out.index("##### ok\n"), out.index("##### bad\n"))
        suite = ET.parse(path).getroot().find("testsuite")
        self.assertEqual(suite.get("tests"), "2")
        self.assertEqual(suite.get("failures"), "1")
        bad, ok = suite.findall("testcase")
        self.assertEqual(bad.get("name"), "bad")
        self.assertEqual(bad.find("system-err").text, "oops\n")
        self.assertIsNotNone(bad.find("failure"))
        self.assertEqual(ok.find("system-out").text, "ok\n")
        self.assertIsNone(ok.find("failure"))

    def test_no_junit_xml_by_default(self):
        tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmpdir)
        old_cwd = os.getcwd()
        os.chdir(tmpdir)
        try:
            _run(["ok=echo ok"])
        finally:
            os.chdir(old_cwd)
        self.assertEqual(os.listdir(tmpdir), [])

    def test_junit_xml_unwritable(self):
        tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmpdir)
        path = os.path.join(tmpdir, "missing_dir", "junit.xml")
        with contextlib.redirect_stderr(io.StringIO()) as err:
            code, out = _run(["--junit_xml=" + path, "ok=echo ok"])
        # The actions passed, but the requested report could not be written.
        self.assertEqual(code, 1)
        self.assertIn("##### ok\n", out)
        self.assertIn("could not write junit report", err.getvalue())


class ActionsFileTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write(self, name, text):
        path = os.path.join(self.tmpdir, name)
        with open(path, "w") as f:
            f.write(text)
        return path

    def test_file_then_command_line_ids(self):
        first = self._write("a.textproto", 'action { name: "f1" script: "true" }')
        second = self._write("b.textproto", 'action { name: "f2" script: "true" }')
        args = main_lib.parse_args(["--actions_file=" + first, "c1=true", "--actions_file", second])
        actions = main_lib.load_actions(args)
        self.assertEqual([(a.name, a.id) for a in actions], [("f1", 1000), ("f2", 1001), ("c1", 1002)])

    def test_file_only(self):
        path = self._write("a.textproto", 'action { name: "f1" script: "echo from_file" }')
        code, out = _run(["--actions_file=" + path])
        self.assertEqual(code, 0)
        self.assertIn("from_file\n", out)

    def test_ignore_error_does_not_fail(self):
        path = self._write("a.textproto", 'action { name: "flaky" script: "exit 4" ignore_error: true }')
        code, out = _run(["--actions_file=" + path, "ok=echo ok"])
        self.assertEqual(code, 0)
        # Still shown as a failure.
        self.assertRegex(out, r"section_start:\d+:flaky\[collapsed=false\]")

    def test_ignore_error_in_junit_xml(self):
        path = self._write("a.textproto", 'action { name: "flaky" script: "exit 4" ignore_error: true }')
        report = os.path.join(self.tmpdir, "junit.xml")
        code, _ = _run(["--actions_file=" + path, "--junit_xml=" + report, "ok=echo ok"])
        self.assertEqual(code, 0)
        suite = ET.parse(report).getroot().find("testsuite")
        self.assertEqual(suite.get("failures"), "1")
        flaky = suite.find("testcase[@name='flaky']")
        self.assertIsNotNone(flaky.find("failure"))
        self.assertIsNotNone(flaky.find("properties/property[@name='ignore_error'][@value='true']"))

    def test_failure_without_ignore_error_fails(self):
        path = self._write("a.textproto", 'action { name: "bad" script: "exit 4" }')
        code, _ = _run(["--actions_file=" + path, "ok=echo ok"])
        self.assertEqual(code, 1)

    def test_duplicate_names(self):
        path = self._write("a.textproto", 'action { name: "x" script: "true" }')
        with contextlib.redirect_stderr(io.StringIO()) as err:
            code, _ = _run(["--actions_file=" + path, "x=true"])
        self.assertEqual(code, 2)
        self.assertIn("duplicate action names: x", err.getvalue())

    def test_bad_file(self):
        path = self._write("a.textproto", "action {")
        with contextlib.redirect_stderr(io.StringIO()) as err:
            code, _ = _run(["--actions_file=" + path])
        self.assertEqual(code, 2)
        self.assertIn("a.textproto", err.getvalue())


if __name__ == "__main__":
    unittest.main()
