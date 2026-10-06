import os
import shutil
import tempfile
import time
import unittest

from run_actions import action as action_lib
from run_actions import runner


class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_run_one_captures_output(self):
        a = action_lib.parse_action("x=echo out; echo err >&2; exit 3", 1000)
        before = int(time.time())
        r = runner.run_one(a)
        after = int(time.time())
        self.assertTrue(before <= r.start_time <= r.end_time <= after)
        self.assertEqual(r.exit_code, 3)
        self.assertEqual(r.stdout, b"out\n")
        self.assertEqual(r.stderr, b"err\n")
        self.assertIs(r.action, a)

    def test_parallel_results_in_order_and_failure_does_not_stop(self):
        actions = action_lib.parse_actions(["a=sleep 0.2; echo a", "b=exit 1", "c=echo c"])
        results = runner.run_parallel(actions)
        self.assertEqual([r.action.name for r in results], ["a", "b", "c"])
        self.assertEqual([r.exit_code for r in results], [0, 1, 0])
        self.assertEqual(results[0].stdout, b"a\n")
        self.assertEqual(results[2].stdout, b"c\n")

    def test_serial_preserves_order_and_continues_after_failure(self):
        log = os.path.join(self.tmpdir, "log")
        actions = action_lib.parse_actions(
            [
                "one=sleep 0.2; echo one >> '%s'" % log,
                "two=echo two >> '%s'; exit 5" % log,
                "three=echo three >> '%s'" % log,
            ]
        )
        results = runner.run_serial(actions)
        self.assertEqual([r.exit_code for r in results], [0, 5, 0])
        with open(log) as f:
            self.assertEqual(f.read(), "one\ntwo\nthree\n")

    def test_parallel_runs_concurrently(self):
        # 'b' waits for a file that 'a' creates; serial order would deadlock
        # (bounded by the timeout loop) and fail.
        marker = os.path.join(self.tmpdir, "marker")
        actions = action_lib.parse_actions(
            [
                "b=for i in $(seq 50); do [ -e '%s' ] && exit 0; sleep 0.1; done; exit 1" % marker,
                "a=touch '%s'" % marker,
            ]
        )
        results = runner.run_parallel(actions)
        self.assertEqual([r.exit_code for r in results], [0, 0])

    def test_spawn_failure(self):
        old_path = os.environ.get("PATH")
        os.environ["PATH"] = self.tmpdir  # no bash here
        try:
            r = runner.run_one(action_lib.parse_action("echo hi", 1000))
        finally:
            os.environ["PATH"] = old_path
        self.assertEqual(r.exit_code, 127)
        self.assertEqual(r.stdout, b"")
        self.assertIn(b"failed to start action", r.stderr)


if __name__ == "__main__":
    unittest.main()
