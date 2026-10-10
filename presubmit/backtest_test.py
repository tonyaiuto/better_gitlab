import contextlib
import io
import json
import os
import tempfile
import unittest

from presubmit import backtest
from presubmit import source_tree

_TREE = """
/TESTING <<<END
action { name: "lint" command: "lint {FILES}" }
test_suite { name: "unit" tests: "//pkg/..." }
presubmit { include_regex: "\\\\.go$" check_action: "lint" check_tests: "unit" }
END
"""

_PRS = [
    {
        "pr": 1,
        "title": "edit",
        "merge_commit_sha": "aaa",
        "merged_at": "2026-10-01T00:00:00Z",
        "files": [
            {"filename": "pkg/a.go", "status": "modified"},
            {"filename": "pkg/gone.go", "status": "removed"},
            {
                "filename": "pkg/new.go",
                "status": "renamed",
                "previous_filename": "pkg/old.go",
            },
        ],
    },
    {
        "pr": 2,
        "title": "docs",
        "merge_commit_sha": "bbb",
        "merged_at": "2026-10-02T00:00:00Z",
        "files": [{"filename": "README.md", "status": "modified"}],
    },
]


class PrChangesTest(unittest.TestCase):
    def test_removed_and_renamed(self):
        self.assertEqual(
            backtest.pr_changes(_PRS[0]["files"]),
            (
                ["pkg/a.go", "pkg/gone.go", "pkg/new.go", "pkg/old.go"],
                ["pkg/gone.go", "pkg/old.go"],
            ),
        )


class BacktestTest(unittest.TestCase):
    def test_jobs_per_pr(self):
        results = backtest.backtest(source_tree.parse_mock_tree(_TREE), _PRS)
        self.assertEqual(
            [(r["pr"], r["title"]) for r in results], [(1, "edit"), (2, "docs")]
        )
        self.assertEqual(
            [j["argv"] for j in results[0]["jobs"]],
            [
                ["run_actions", "--", "lint=lint pkg/a.go pkg/new.go"],
                ["bazel", "test", "--", "//pkg/..."],
            ],
        )
        self.assertEqual(results[1]["jobs"], [])

    def test_error_kept_per_pr(self):
        tree = source_tree.parse_mock_tree("""
/TESTING <<<END
presubmit { check_action: "nope" }
END
""")
        results = backtest.backtest(tree, _PRS[1:])
        self.assertIn("nope", results[0]["error"])
        self.assertNotIn("jobs", results[0])

    def test_summary(self):
        results = backtest.backtest(source_tree.parse_mock_tree(_TREE), _PRS)
        self.assertEqual(
            backtest.summary(results).splitlines(),
            [
                "2 PRs: 1 with jobs, 1 with no jobs, 0 errors",
                "     1  actions:default",
                "     1  bazel:test",
            ],
        )


class MainTest(unittest.TestCase):
    def test_reads_file_writes_out(self):
        with tempfile.TemporaryDirectory() as root:
            with open(os.path.join(root, "TESTING"), "w") as f:
                f.write(
                    'action { name: "lint" command: "lint {FILES}" }\n'
                    'presubmit { check_action: "lint" }\n'
                )
            prs_path = os.path.join(root, "prs.json")
            with open(prs_path, "w") as f:
                json.dump(_PRS, f)
            out_path = os.path.join(root, "out.json")
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code = backtest.main(
                    [prs_path, "--repo", root, "--pr", "2", "--out", out_path]
                )
            self.assertEqual(code, 0)
            with open(out_path) as f:
                results = json.load(f)
            self.assertEqual([r["pr"] for r in results], [2])
            self.assertEqual(
                results[0]["jobs"][0]["argv"],
                ["run_actions", "--", "lint=lint README.md"],
            )
            self.assertIn("1 PRs: 1 with jobs", err.getvalue())


if __name__ == "__main__":
    unittest.main()
