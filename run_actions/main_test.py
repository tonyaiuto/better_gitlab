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


if __name__ == "__main__":
    unittest.main()
