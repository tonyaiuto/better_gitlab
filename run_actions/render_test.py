import io
import unittest

from run_actions import render
from run_actions.action import Action, ActionResult


def _result(id, name, exit_code, stdout=b"", stderr=b""):
    return ActionResult(Action(id, name, "cmd"), exit_code, stdout, stderr, start_time=1700000000, end_time=1700000005)


class RenderTest(unittest.TestCase):
    def test_exact_bytes_one_section(self):
        out = io.BytesIO()
        render.render([_result(1000, "ls /", 0, b"hi\n", b"warn\n")], True, out)
        self.assertEqual(
            out.getvalue(),
            b"##### ls /\n"
            b"\x1b[0Ksection_start:1700000000:ls__-1000[collapsed=true]\r\x1b[0K"
            b"\x1b[36;1mRunning ls /\x1b[0;m\n"
            b"hi\n"
            b"warn\n"
            b"\x1b[0Ksection_end:1700000005:ls__-1000\r\x1b[0K\n",
        )

    def test_failed_section_not_collapsed(self):
        out = io.BytesIO()
        render.render([_result(1001, "bad", 2)], True, out)
        self.assertIn(b"section_start:1700000000:bad-1001[collapsed=false]\r", out.getvalue())

    def test_missing_trailing_newlines_added(self):
        out = io.BytesIO()
        render.render([_result(1000, "x", 0, b"out", b"err")], True, out)
        self.assertTrue(out.getvalue().endswith(b"\x1b[0;m\nout\nerr\n\x1b[0Ksection_end:1700000005:x-1000\r\x1b[0K\n"))

    def test_raw_bytes_passed_through(self):
        out = io.BytesIO()
        render.render([_result(1000, "x", 0, b"\xff\xfe\x1b[31mred\n")], True, out)
        self.assertIn(b"\xff\xfe\x1b[31mred\n\x1b[0Ksection_end", out.getvalue())

    def test_name_with_braces(self):
        out = io.BytesIO()
        render.render([_result(1000, "echo {x}", 0)], True, out)
        self.assertTrue(out.getvalue().startswith(b"##### echo {x}\n"))

    def _order(self, show_errors_last):
        results = [
            _result(1000, "a", 1),
            _result(1001, "b", 0),
            _result(1002, "c", 2),
            _result(1003, "d", 0),
        ]
        return [r.action.name for r in render.order_results(results, show_errors_last)]

    def test_order_errors_last(self):
        self.assertEqual(self._order(True), ["b", "d", "a", "c"])

    def test_order_command_line(self):
        self.assertEqual(self._order(False), ["a", "b", "c", "d"])


if __name__ == "__main__":
    unittest.main()
