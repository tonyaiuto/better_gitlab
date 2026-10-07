import os
import subprocess
import tempfile
import unittest

from presubmit import changed_files
from presubmit.changed_files import ChangedFilesError


class FixedChangedFilesTest(unittest.TestCase):
    def test_sorted_unique_normalized(self):
        files = changed_files.FixedChangedFiles(["/b/x.c", "a.c", "b/./x.c"])
        self.assertEqual(files.get(), ["a.c", "b/x.c"])


class GitDiffChangedFilesTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = self.dir.name
        self.git("init", "-q")
        self.write("keep.c", "keep")
        self.write("src/edit.c", "old")
        self.write("src/delete.c", "x")
        self.write("old/moved.c", "moved")
        self.write("unchanged/a.c", "a")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")
        self.git("tag", "base")

    def tearDown(self):
        self.dir.cleanup()

    def git(self, *args):
        env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", HOME=self.root)
        subprocess.run(
            ["git", "-C", self.root,
             "-c", "user.name=test", "-c", "user.email=test@example.com",
             "-c", "commit.gpgsign=false"] + list(args),
            check=True, env=env, capture_output=True)

    def write(self, path, content):
        full = os.path.join(self.root, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(content)

    def test_committed_changes(self):
        self.write("src/edit.c", "new")
        self.write("src/new file.c", "spaces in name")
        os.remove(os.path.join(self.root, "src/delete.c"))
        os.makedirs(os.path.join(self.root, "new"))
        self.git("mv", "old/moved.c", "new/moved.c")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "change")

        files = changed_files.GitDiffChangedFiles("base", repo_root=self.root)
        self.assertEqual(
            files.get(),
            ["new/moved.c", "old/moved.c", "src/delete.c", "src/edit.c", "src/new file.c"])

    def test_uncommitted_changes_included(self):
        self.write("src/edit.c", "dirty")
        files = changed_files.GitDiffChangedFiles("base", repo_root=self.root)
        self.assertEqual(files.get(), ["src/edit.c"])

    def test_no_changes(self):
        files = changed_files.GitDiffChangedFiles("base", repo_root=self.root)
        self.assertEqual(files.get(), [])

    def test_bad_ref(self):
        files = changed_files.GitDiffChangedFiles("no-such-ref", repo_root=self.root)
        with self.assertRaises(ChangedFilesError) as cm:
            files.get()
        self.assertIn("no-such-ref", str(cm.exception))

    def test_missing_git(self):
        files = changed_files.GitDiffChangedFiles(
            "base", repo_root=self.root, git="/no/such/git")
        with self.assertRaises(ChangedFilesError):
            files.get()


if __name__ == "__main__":
    unittest.main()
