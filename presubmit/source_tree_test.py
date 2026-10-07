import os
import tempfile
import unittest

from presubmit import source_tree
from presubmit.source_tree import SourceTreeError

_SPEC = """
/src/main/foo.c
/src/main/lib/bar.c
/src/main/TESTING <<<CONTENT
presubmit {
  check_action: "lint"
}
CONTENT
# A comment.

/src/common/baz.c
"""


class NormalizePathTest(unittest.TestCase):
    def test_leading_slash_is_tree_root(self):
        self.assertEqual(source_tree.normalize_path("/src/a.c"), "src/a.c")

    def test_normalizes(self):
        self.assertEqual(source_tree.normalize_path("src/./x/../a.c"), "src/a.c")

    def test_rejects_leaving_tree(self):
        with self.assertRaises(SourceTreeError):
            source_tree.normalize_path("../a.c")
        with self.assertRaises(SourceTreeError):
            source_tree.normalize_path("src/../../a.c")

    def test_rejects_empty(self):
        with self.assertRaises(SourceTreeError):
            source_tree.normalize_path("/")


class ParseMockTreeTest(unittest.TestCase):
    def test_spec(self):
        tree = source_tree.parse_mock_tree(_SPEC)
        self.assertEqual(
            tree.paths(),
            ["src/common/baz.c", "src/main/TESTING", "src/main/foo.c", "src/main/lib/bar.c"])
        self.assertEqual(tree.read("src/main/foo.c"), "")
        self.assertEqual(
            tree.read("/src/main/TESTING"),
            'presubmit {\n  check_action: "lint"\n}\n')

    def test_exists(self):
        tree = source_tree.parse_mock_tree(_SPEC)
        self.assertTrue(tree.exists("src/main/TESTING"))
        self.assertTrue(tree.exists("/src/main/TESTING"))
        self.assertFalse(tree.exists("src/TESTING"))
        # Directories are not files.
        self.assertFalse(tree.exists("src/main"))

    def test_read_missing(self):
        tree = source_tree.parse_mock_tree(_SPEC)
        with self.assertRaises(FileNotFoundError):
            tree.read("nope.c")

    def test_empty_heredoc(self):
        tree = source_tree.parse_mock_tree("a/TESTING <<<END\nEND\n")
        self.assertEqual(tree.read("a/TESTING"), "")

    def test_heredoc_keeps_blank_and_comment_lines(self):
        tree = source_tree.parse_mock_tree("a/TESTING <<<END\n# c\n\nx\nEND\n")
        self.assertEqual(tree.read("a/TESTING"), "# c\n\nx\n")

    def test_tag_must_match_whole_line(self):
        tree = source_tree.parse_mock_tree("a <<<END\n  END\nEND\n")
        self.assertEqual(tree.read("a"), "  END\n")

    def test_unterminated_heredoc(self):
        with self.assertRaises(SourceTreeError) as cm:
            source_tree.parse_mock_tree("x\na/TESTING <<<END\nstuff\n")
        self.assertIn("line 2", str(cm.exception))

    def test_duplicate_path(self):
        with self.assertRaises(SourceTreeError) as cm:
            source_tree.parse_mock_tree("/a.c\na.c\n")
        self.assertIn("duplicate", str(cm.exception))

    def test_bad_path(self):
        with self.assertRaises(SourceTreeError) as cm:
            source_tree.parse_mock_tree("../a.c\n")
        self.assertIn("line 1", str(cm.exception))


class FsSourceTreeTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        os.makedirs(os.path.join(self.dir.name, "src", "main"))
        with open(os.path.join(self.dir.name, "src", "main", "TESTING"), "w") as f:
            f.write("include: \"x\"\n")
        self.tree = source_tree.FsSourceTree(self.dir.name)

    def tearDown(self):
        self.dir.cleanup()

    def test_exists(self):
        self.assertTrue(self.tree.exists("src/main/TESTING"))
        self.assertTrue(self.tree.exists("/src/main/TESTING"))
        self.assertFalse(self.tree.exists("src/main"))
        self.assertFalse(self.tree.exists("src/TESTING"))

    def test_read(self):
        self.assertEqual(self.tree.read("src/main/TESTING"), "include: \"x\"\n")

    def test_read_missing(self):
        with self.assertRaises(FileNotFoundError):
            self.tree.read("src/nope")

    def test_rejects_leaving_tree(self):
        with self.assertRaises(SourceTreeError):
            self.tree.exists("../etc/passwd")


if __name__ == "__main__":
    unittest.main()
