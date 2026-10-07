import unittest

from presubmit import discover
from presubmit import loader
from presubmit import plan
from presubmit import selection
from presubmit import source_tree
from presubmit.plan import PlanError, PlannedAction, TestRun


def _plan(spec, changed, **kwargs):
    tree = source_tree.parse_mock_tree(spec)
    loaded = loader.load(tree, discover.find_testing_files(tree, changed))
    return plan.build_plan(loaded, selection.select(loaded, changed), **kwargs)


class ExpandCommandTest(unittest.TestCase):
    def test_files(self):
        self.assertEqual(
            plan.expand_command("x", "lint {FILES} --strict", ["a.c", "b c.c"]),
            ["lint a.c 'b c.c' --strict"])

    def test_each_file(self):
        self.assertEqual(
            plan.expand_command("x", "fmt --check {EACH_FILE}", ["a.c", "b c.c"]),
            ["fmt --check a.c", "fmt --check 'b c.c'"])

    def test_placeholder_used_twice(self):
        self.assertEqual(
            plan.expand_command("x", "cp {EACH_FILE} {EACH_FILE}.bak", ["a"]),
            ["cp a a.bak"])

    def test_no_placeholder(self):
        self.assertEqual(plan.expand_command("x", "make lint", ["a.c", "b.c"]), ["make lint"])

    def test_other_braces_untouched(self):
        self.assertEqual(
            plan.expand_command("x", "echo ${HOME} {other} {FILES}", ["a"]),
            ["echo ${HOME} {other} a"])

    def test_both_placeholders(self):
        with self.assertRaises(PlanError):
            plan.expand_command("x", "{FILES} {EACH_FILE}", ["a"])


class BuildPlanActionsTest(unittest.TestCase):
    def test_default_machine_types(self):
        p = _plan("""
/TESTING <<<END
action { name: "lint" command: "lint {FILES}" }
presubmit { check_action: "lint" }
END
""", ["a.c"])
        self.assertEqual(p.actions, [PlannedAction("lint", "default", ["a.c"], ["lint a.c"])])
        self.assertEqual(p.test_runs, [])

    def test_custom_default_machine_types(self):
        p = _plan("""
/TESTING <<<END
action { name: "lint" command: "lint" }
presubmit { check_action: "lint" }
END
""", ["a.c"], default_machine_types=["linux", "mac"])
        self.assertEqual([(a.name, a.machine_type) for a in p.actions],
                         [("lint", "linux"), ("lint", "mac")])

    def test_one_per_machine_type(self):
        p = _plan("""
/TESTING <<<END
action { name: "build" command: "make" machine_type: "linux_arm64" machine_type: "linux_amd64" }
presubmit { check_action: "build" }
END
""", ["a.c"])
        self.assertEqual(p.actions, [
            PlannedAction("build", "linux_amd64", ["a.c"], ["make"]),
            PlannedAction("build", "linux_arm64", ["a.c"], ["make"]),
        ])

    def test_same_action_from_several_blocks_unions_files(self):
        p = _plan("""
/TESTING <<<END
action { name: "lint" command: "lint {FILES}" }
END
/a/TESTING <<<END
presubmit { check_action: "lint" }
END
/b/TESTING <<<END
presubmit { include_regex: "\\\\.c$" check_action: "lint" }
END
""", ["a/x.c", "b/y.c", "b/y.h"])
        self.assertEqual(p.actions, [
            PlannedAction("lint", "default", ["a/x.c", "b/y.c"], ["lint a/x.c b/y.c"]),
        ])

    def test_each_file_after_union(self):
        p = _plan("""
/TESTING <<<END
action { name: "fmt" command: "fmt {EACH_FILE}" }
END
/a/TESTING <<<END
presubmit { check_action: "fmt" }
END
/b/TESTING <<<END
presubmit { check_action: "fmt" }
END
""", ["b/y.c", "a/x.c"])
        self.assertEqual(p.actions[0].commands, ["fmt a/x.c", "fmt b/y.c"])

    def test_actions_sorted_by_name(self):
        p = _plan("""
/TESTING <<<END
action { name: "zeta" command: "z" }
action { name: "alpha" command: "a" }
presubmit { check_action: "zeta" check_action: "alpha" }
END
""", ["a.c"])
        self.assertEqual([a.name for a in p.actions], ["alpha", "zeta"])


class BuildPlanTestRunsTest(unittest.TestCase):
    def test_no_platform(self):
        p = _plan("""
/TESTING <<<END
test_suite { name: "unit" tests: "//b/..." tests: "//a/..." }
presubmit { check_tests: "unit" }
END
""", ["a.c"])
        self.assertEqual(p.test_runs, [TestRun("", [], ["//a/...", "//b/..."], ["unit"])])
        self.assertEqual(p.actions, [])

    def test_one_run_per_platform(self):
        p = _plan("""
/TESTING <<<END
test_suite { name: "unit" tests: "//..." platform: "//p:linux" platform: "//p:mac" }
presubmit { check_tests: "unit" }
END
""", ["a.c"])
        self.assertEqual(p.test_runs, [
            TestRun("//p:linux", [], ["//..."], ["unit"]),
            TestRun("//p:mac", [], ["//..."], ["unit"]),
        ])

    def test_same_args_and_platform_merge(self):
        p = _plan("""
/TESTING <<<END
test_suite { name: "a_tests" tests: "//a/..." test_args: "--test_output=errors" }
test_suite { name: "b_tests" tests: "//b/..." test_args: "--test_output=errors" }
test_suite { name: "c_tests" tests: "//c/..." }
test_suite { name: "d_tests" tests: "//a/..." platform: "//p:linux" }
presubmit { check_tests: "a_tests" check_tests: "b_tests" check_tests: "c_tests" }
presubmit { check_tests: "d_tests" }
END
""", ["x.c"])
        self.assertEqual(p.test_runs, [
            TestRun("", [], ["//c/..."], ["c_tests"]),
            TestRun("", ["--test_output=errors"], ["//a/...", "//b/..."], ["a_tests", "b_tests"]),
            TestRun("//p:linux", [], ["//a/..."], ["d_tests"]),
        ])

    def test_test_args_order_matters(self):
        p = _plan("""
/TESTING <<<END
test_suite { name: "a" tests: "//a" test_args: "-x" test_args: "-y" }
test_suite { name: "b" tests: "//b" test_args: "-y" test_args: "-x" }
presubmit { check_tests: "a" check_tests: "b" }
END
""", ["x.c"])
        self.assertEqual(len(p.test_runs), 2)

    def test_suite_selected_twice_counted_once(self):
        p = _plan("""
/TESTING <<<END
test_suite { name: "unit" tests: "//..." }
presubmit { check_tests: "unit" }
END
/a/TESTING <<<END
presubmit { check_tests: "unit" }
END
""", ["a/x.c"])
        self.assertEqual(p.test_runs, [TestRun("", [], ["//..."], ["unit"])])


class BuildPlanEmptyTest(unittest.TestCase):
    def test_nothing_selected(self):
        p = _plan("""
/TESTING <<<END
action { name: "lint" command: "lint" }
presubmit { include_regex: "\\\\.go$" check_action: "lint" }
END
""", ["a.c"])
        self.assertEqual(p.actions, [])
        self.assertEqual(p.test_runs, [])


if __name__ == "__main__":
    unittest.main()
