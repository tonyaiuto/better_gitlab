import unittest

from presubmit import jobs
from presubmit.jobs import Job, JobAction
from presubmit.plan import Plan, PlannedAction, TestRun


def _jobs(actions=(), test_runs=()):
    return jobs.build_jobs(Plan(actions=list(actions), test_runs=list(test_runs)))


class RunActionsNameTest(unittest.TestCase):
    def test_legal_unchanged(self):
        self.assertEqual(jobs.run_actions_name("lint_go-1.2"), "lint_go-1.2")

    def test_illegal_chars(self):
        self.assertEqual(jobs.run_actions_name("lint:go files"), "lint_go_files")

    def test_leading_digit(self):
        self.assertEqual(jobs.run_actions_name("2fa"), "_2fa")


class RunActionsJobsTest(unittest.TestCase):
    def test_one_job_per_machine_type(self):
        got = _jobs(
            [
                PlannedAction("build", "linux", ["a.c"], ["make"]),
                PlannedAction("lint", "default", ["a.c"], ["lint a.c"]),
                PlannedAction("test", "linux", [], ["make test"]),
            ]
        )
        self.assertEqual(
            got,
            [
                Job(
                    name="actions:default",
                    kind="run_actions",
                    argv=["run_actions", "--", "lint=lint a.c"],
                    machine_type="default",
                    actions=[JobAction("lint", "lint", "lint a.c")],
                ),
                Job(
                    name="actions:linux",
                    kind="run_actions",
                    argv=["run_actions", "--", "build=make", "test=make test"],
                    machine_type="linux",
                    actions=[
                        JobAction("build", "build", "make"),
                        JobAction("test", "test", "make test"),
                    ],
                ),
            ],
        )

    def test_each_file_numbered(self):
        got = _jobs(
            [PlannedAction("fmt", "default", ["a.c", "b.c"], ["fmt a.c", "fmt b.c"])]
        )
        self.assertEqual(
            got[0].argv, ["run_actions", "--", "fmt.1=fmt a.c", "fmt.2=fmt b.c"]
        )
        self.assertEqual([a.action for a in got[0].actions], ["fmt", "fmt"])

    def test_action_without_commands_dropped(self):
        got = _jobs(
            [
                PlannedAction("lint", "default", ["gone.c"], []),
                PlannedAction("vet", "mac", ["gone.c"], []),
                PlannedAction("gen", "default", ["gone.c"], ["make gen"]),
            ]
        )
        self.assertEqual(
            [(j.name, [a.name for a in j.actions]) for j in got],
            [("actions:default", ["gen"])],
        )

    def test_name_made_legal(self):
        got = _jobs([PlannedAction("lint:go", "default", ["a.go"], ["golint"])])
        self.assertEqual(got[0].argv, ["run_actions", "--", "lint_go=golint"])
        self.assertEqual(got[0].actions, [JobAction("lint_go", "lint:go", "golint")])

    def test_custom_runner(self):
        got = jobs.build_jobs(
            Plan(
                actions=[PlannedAction("lint", "default", [], ["lint"])], test_runs=[]
            ),
            run_actions_command=["python3", "run_actions.zip", "--ddci"],
        )
        self.assertEqual(
            got[0].argv, ["python3", "run_actions.zip", "--ddci", "--", "lint=lint"]
        )


class BazelJobsTest(unittest.TestCase):
    def test_test_and_coverage(self):
        got = _jobs(
            test_runs=[
                TestRun(
                    "",
                    ["--test_output=errors"],
                    ["//cmd/...", "//pkg/..."],
                    ["a", "b"],
                    False,
                ),
                TestRun("", [], ["//pkg/..."], ["cov"], True),
            ]
        )
        self.assertEqual(
            got,
            [
                Job(
                    name="bazel:coverage",
                    kind="bazel",
                    argv=["bazel", "coverage", "--", "//pkg/..."],
                    tests=["//pkg/..."],
                    suites=["cov"],
                ),
                Job(
                    name="bazel:test",
                    kind="bazel",
                    argv=[
                        "bazel",
                        "test",
                        "--test_output=errors",
                        "--",
                        "//cmd/...",
                        "//pkg/...",
                    ],
                    tests=["//cmd/...", "//pkg/..."],
                    suites=["a", "b"],
                ),
            ],
        )

    def test_platform(self):
        got = _jobs(test_runs=[TestRun("//p:linux", [], ["//e2e/..."], ["e2e"], False)])
        self.assertEqual(got[0].name, "bazel:test://p:linux")
        self.assertEqual(
            got[0].argv, ["bazel", "test", "--platforms=//p:linux", "--", "//e2e/..."]
        )
        self.assertEqual(got[0].platform, "//p:linux")

    def test_same_name_numbered(self):
        got = _jobs(
            test_runs=[
                TestRun("", [], ["//a/..."], ["a"], False),
                TestRun("", ["--config=race"], ["//b/..."], ["b"], False),
            ]
        )
        self.assertEqual([j.name for j in got], ["bazel:test:1", "bazel:test:2"])

    def test_no_patterns_dropped(self):
        self.assertEqual(_jobs(test_runs=[TestRun("", [], [], ["empty"], False)]), [])


class OrderTest(unittest.TestCase):
    def test_actions_before_bazel(self):
        got = _jobs(
            [PlannedAction("lint", "default", [], ["lint"])],
            [TestRun("", [], ["//..."], ["all"], False)],
        )
        self.assertEqual([j.kind for j in got], ["run_actions", "bazel"])


if __name__ == "__main__":
    unittest.main()
