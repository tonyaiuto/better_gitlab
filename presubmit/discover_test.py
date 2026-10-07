import unittest

from presubmit import discover
from presubmit import source_tree

# A TESTING file in every directory on the way to foo/bar/baz/ball/bat/foo.c,
# plus some that should not apply.
_TREE = source_tree.parse_mock_tree("""
/TESTING
/foo/TESTING
/foo/bar/TESTING
/foo/bar/baz/TESTING
/foo/bar/baz/ball/TESTING
/foo/bar/baz/ball/bat/TESTING
/foo/bar/baz/ball/bat/foo.c
/foo/other/TESTING
/foo/other/x.c
/foobar/TESTING
/foobar/y.c
/docs/README.md
/docs/METADATA
/foo/METADATA
""")


class AncestorDirsTest(unittest.TestCase):
    def test_nested(self):
        self.assertEqual(discover.ancestor_dirs("a/b/c.c"), ["a/b", "a", ""])

    def test_root_file(self):
        self.assertEqual(discover.ancestor_dirs("c.c"), [""])


class FindTestingFilesTest(unittest.TestCase):
    def test_every_level_applies(self):
        self.assertEqual(
            discover.find_testing_files(_TREE, ["foo/bar/baz/ball/bat/foo.c"]),
            [
                "TESTING",
                "foo/TESTING",
                "foo/bar/TESTING",
                "foo/bar/baz/TESTING",
                "foo/bar/baz/ball/TESTING",
                "foo/bar/baz/ball/bat/TESTING",
            ])

    def test_gaps_in_the_chain(self):
        tree = source_tree.parse_mock_tree("/a/TESTING\n/a/b/c/TESTING\n/a/b/c/d/e.c\n")
        self.assertEqual(
            discover.find_testing_files(tree, ["a/b/c/d/e.c"]),
            ["a/TESTING", "a/b/c/TESTING"])

    def test_siblings_do_not_apply(self):
        # foobar/ is not under foo/, and foo/other/ is not an ancestor.
        self.assertEqual(
            discover.find_testing_files(_TREE, ["foobar/y.c"]),
            ["TESTING", "foobar/TESTING"])

    def test_several_files_root_first_no_duplicates(self):
        self.assertEqual(
            discover.find_testing_files(
                _TREE, ["foo/other/x.c", "foobar/y.c", "foo/bar/new.c"]),
            ["TESTING", "foo/TESTING", "foobar/TESTING", "foo/bar/TESTING", "foo/other/TESTING"])

    def test_deleted_file_still_finds_testing(self):
        # The changed file need not exist in the tree.
        self.assertEqual(
            discover.find_testing_files(_TREE, ["foo/other/gone.c"]),
            ["TESTING", "foo/TESTING", "foo/other/TESTING"])

    def test_changed_testing_file_applies_to_itself(self):
        self.assertEqual(
            discover.find_testing_files(_TREE, ["foo/other/TESTING"]),
            ["TESTING", "foo/TESTING", "foo/other/TESTING"])

    def test_other_filename(self):
        self.assertEqual(
            discover.find_testing_files(_TREE, ["foo/bar/a.c", "docs/README.md"], "METADATA"),
            ["docs/METADATA", "foo/METADATA"])

    def test_bad_filename(self):
        with self.assertRaises(ValueError):
            discover.find_testing_files(_TREE, ["a.c"], "x/TESTING")

    def test_no_changes(self):
        self.assertEqual(discover.find_testing_files(_TREE, []), [])


class ScopeTest(unittest.TestCase):
    def test_root_testing_applies_to_everything(self):
        self.assertTrue(discover.in_scope("TESTING", "a.c"))
        self.assertTrue(discover.in_scope("TESTING", "x/y/z.c"))

    def test_subdirectory(self):
        self.assertTrue(discover.in_scope("foo/TESTING", "foo/a.c"))
        self.assertTrue(discover.in_scope("foo/TESTING", "foo/b/c.c"))
        self.assertFalse(discover.in_scope("foo/TESTING", "foobar/a.c"))
        self.assertFalse(discover.in_scope("foo/TESTING", "a.c"))

    def test_files_in_scope(self):
        self.assertEqual(
            discover.files_in_scope("foo/TESTING", ["a.c", "foo/a.c", "foobar/a.c", "foo/b/c.c"]),
            ["foo/a.c", "foo/b/c.c"])


if __name__ == "__main__":
    unittest.main()
