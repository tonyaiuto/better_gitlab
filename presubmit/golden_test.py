"""Runs each testdata/*.test case through the whole pipeline.

A case file has sections, each starting with a line "== NAME":

    == tree       a mock source tree (see source_tree.parse_mock_tree)
    == changed    the changed files, one per line
    == deleted    optional: files the PR deletes, one per line; they are
                  appended to the changed files
    == expected   the expected JSON result of cli.compute. Only the keys it
                  lists are compared, so a case can leave out e.g. "jobs".
    == error      instead of expected: text the error message must contain

Lines before the first section are a free-form description.
"""

import glob
import json
import os
import unittest

from presubmit import cli
from presubmit import source_tree

_TESTDATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "testdata")


def parse_case(text):
    sections = {}
    current = None
    for line in text.splitlines(keepends=True):
        if line.startswith("== "):
            current = line[3:].strip()
            sections[current] = ""
        elif current:
            sections[current] += line
    return sections


def _lines(text):
    return [l.strip() for l in text.splitlines() if l.strip()]


class GoldenTest(unittest.TestCase):
    def test_cases_exist(self):
        self.assertTrue(glob.glob(os.path.join(_TESTDATA, "*.test")))

    def test_cases(self):
        for path in sorted(glob.glob(os.path.join(_TESTDATA, "*.test"))):
            with self.subTest(case=os.path.basename(path)):
                with open(path, encoding="utf-8") as f:
                    case = parse_case(f.read())
                tree = source_tree.parse_mock_tree(case["tree"])
                changed = _lines(case["changed"])
                deleted = _lines(case.get("deleted", ""))
                # As with FixedChangedFiles, deleted files are also changed files.
                changed += [d for d in deleted if d not in changed]
                if "error" in case:
                    with self.assertRaises(Exception) as cm:
                        cli.compute(tree, changed, deleted_files=deleted)
                    self.assertIn(case["error"].strip(), str(cm.exception))
                else:
                    expected = json.loads(case["expected"])
                    got = cli.compute(tree, changed, deleted_files=deleted)
                    self.assertEqual({k: got[k] for k in expected}, expected)


if __name__ == "__main__":
    unittest.main()
