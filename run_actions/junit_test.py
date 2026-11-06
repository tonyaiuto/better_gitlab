import os
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET

from run_actions import action as action_lib
from run_actions import junit


def _result(name, exit_code, stdout=b"", stderr=b"", id=1000, duration=0.5):
    return action_lib.ActionResult(
        action=action_lib.Action(id=id, name=name, command="cmd " + name),
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        start_time=1700000000 + id,
        end_time=1700000001 + id,
        duration=duration,
    )


def _properties(testcase):
    found = {}
    for prop in testcase.iter("property"):
        found[prop.get("name")] = prop.get("value")
    return found


class CleanTextTest(unittest.TestCase):
    def test_strips_ansi_and_illegal_chars(self):
        self.assertEqual(junit.clean_text(b"\x1b[36;1mhi\x1b[0;m\x00\x07 there\n"), "hi there\n")

    def test_keeps_tabs_and_newlines(self):
        self.assertEqual(junit.clean_text(b"a\tb\r\nc"), "a\tb\r\nc")

    def test_invalid_utf8(self):
        self.assertEqual(junit.clean_text(b"a\xffb"), "a�b")


class BuildTest(unittest.TestCase):
    def test_counts_and_testcases(self):
        results = [
            _result("ok", 0, stdout=b"out\n", id=1000, duration=1.25),
            _result("bad", 3, stderr=b"err\n", id=1001),
            _result("gone", 127, id=1002),
        ]
        root = junit.build(results, wall_time=2.5).getroot()
        self.assertEqual(root.tag, "testsuites")
        suite = root.find("testsuite")
        for element in (root, suite):
            self.assertEqual(element.get("tests"), "3")
            self.assertEqual(element.get("failures"), "1")
            self.assertEqual(element.get("errors"), "1")
            self.assertEqual(element.get("time"), "2.500")
            self.assertEqual(element.get("timestamp"), "2023-11-14T22:30:00Z")

        cases = suite.findall("testcase")
        self.assertEqual([c.get("name") for c in cases], ["ok", "bad", "gone"])
        ok, bad, gone = cases

        self.assertEqual(ok.get("time"), "1.250")
        self.assertIsNone(ok.find("failure"))
        self.assertIsNone(ok.find("error"))
        self.assertEqual(ok.find("system-out").text, "out\n")
        self.assertIsNone(ok.find("system-err"))
        self.assertEqual(_properties(ok), {"action_id": "1000", "command": "cmd ok", "exit_code": "0"})

        self.assertEqual(bad.find("failure").get("message"), "exit code 3")
        self.assertEqual(bad.find("system-err").text, "err\n")
        self.assertIsNone(bad.find("system-out"))

        self.assertEqual(gone.find("error").get("type"), "SpawnFailure")
        self.assertIsNone(gone.find("failure"))

    def test_empty(self):
        root = junit.build([], wall_time=0).getroot()
        self.assertEqual(root.get("tests"), "0")
        self.assertIsNone(root.get("timestamp"))

    def test_all_pass(self):
        root = junit.build([_result("a", 0, id=1000), _result("b", 0, id=1001)], wall_time=1).getroot()
        self.assertEqual(root.get("tests"), "2")
        self.assertEqual(root.get("failures"), "0")
        self.assertEqual(root.get("errors"), "0")
        self.assertEqual(root.find("testsuite").get("skipped"), "0")

    def test_timestamp_is_earliest_start(self):
        results = [_result("late", 0, id=1005), _result("early", 0, id=1001)]
        root = junit.build(results, wall_time=1).getroot()
        self.assertEqual(root.get("timestamp"), junit._timestamp(1700000000 + 1001))

    def test_wall_time_not_sum_of_durations(self):
        # Parallel actions: each took 2s, but the run took 2s, not 4s.
        results = [_result("a", 0, id=1000, duration=2), _result("b", 0, id=1001, duration=2)]
        root = junit.build(results, wall_time=2).getroot()
        self.assertEqual(root.get("time"), "2.000")
        self.assertEqual([c.get("time") for c in root.iter("testcase")], ["2.000", "2.000"])

    def test_suite_name(self):
        root = junit.build([_result("a", 0)], wall_time=1, suite_name="lint").getroot()
        self.assertEqual(root.get("name"), "lint")
        self.assertEqual(root.find("testsuite").get("name"), "lint")
        self.assertEqual(root.find("testsuite/testcase").get("classname"), "lint")

    def test_output_that_is_only_escapes_is_omitted(self):
        testcase = junit.build([_result("a", 0, stdout=b"\x1b[0m", stderr=b"\x00")], 1).getroot().find(
            "testsuite/testcase"
        )
        self.assertIsNone(testcase.find("system-out"))
        self.assertIsNone(testcase.find("system-err"))

    def test_command_property_is_cleaned(self):
        result = _result("a", 0)
        result.action.command = "printf '\x1b[31mred'"
        testcase = junit.build([result], 1).getroot().find("testsuite/testcase")
        self.assertEqual(_properties(testcase)["command"], "printf 'red'")


class WriteTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_round_trip_with_hostile_output(self):
        path = os.path.join(self.tmpdir, "junit.xml")
        output = b"<tag> & \x1b[31mred\x1b[0m \x00\xfe\n"
        junit.write([_result("x", 1, stdout=output)], 1.0, path)
        with open(path, "rb") as f:
            self.assertTrue(f.read().startswith(b"<?xml"))
        testcase = ET.parse(path).getroot().find("testsuite/testcase")
        self.assertEqual(testcase.find("system-out").text, "<tag> & red �\n")


if __name__ == "__main__":
    unittest.main()
