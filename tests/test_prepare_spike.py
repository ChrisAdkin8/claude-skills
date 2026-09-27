"""Tests for skills/spec/scripts/prepare-spike.sh: it deletes and fills only a spike's own scratch
directory under ~/.cache/spec-spikes, whatever arguments it's given.

Run with: python3 -m unittest discover -s ~/code/github.com/claude-skills/tests
"""

import os
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "spec" / "scripts" / "prepare-spike.sh"


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


class PrepareSpike(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        (self.repo / "a.txt").write_text("at read-at\n")
        git(self.repo, "add", "a.txt")
        git(
            self.repo,
            "-c", "user.email=t@local", "-c", "user.name=t",
            "commit", "-qm", "one",
        )  # fmt: skip
        self.sha = git(self.repo, "rev-parse", "--short", "HEAD")
        (self.repo / "a.txt").write_text("edited since\n")
        # A home of its own, so the script's `rm -rf` never runs in the real ~/.cache.
        self.home = self.tmp.resolve() / "home"
        self.home.mkdir()
        self.env = {**os.environ, "HOME": str(self.home)}
        self.root = self.home / ".cache" / "spec-spikes"
        self.name = f"test-prepare-spike-{uuid.uuid4().hex[:8]}"
        self.scratch = self.root / self.name / "spec" / "S1"

    def prepare(self, *args):
        """(exit code, stdout + stderr) from prepare-spike.sh."""
        run = subprocess.run(
            [str(SCRIPT), *map(str, args)], capture_output=True, text=True, check=False,
            env=self.env,
        )  # fmt: skip
        return run.returncode, run.stdout + run.stderr

    def test_exports_the_repo_at_read_at(self):
        (self.scratch / "src").mkdir(parents=True)
        (self.scratch / "old.txt").write_text("from an earlier run\n")
        code, out = self.prepare(self.scratch, self.repo, self.sha)
        self.assertEqual(code, 0, out)
        self.assertEqual((self.scratch / "src" / "a.txt").read_text(), "at read-at\n")
        self.assertFalse((self.scratch / "old.txt").exists())

    def test_read_at_none_only_clears(self):
        code, out = self.prepare(self.scratch, "none", "none")
        self.assertEqual(code, 0, out)
        self.assertTrue(self.scratch.is_dir())
        self.assertFalse((self.scratch / "src").exists())

    def test_refuses_paths_outside_its_scratch_layout(self):
        victim = self.tmp / "victim"
        victim.mkdir()
        for scratch in (
            victim,  # anywhere else
            self.root / self.name / "S1",  # a level missing
            self.root / self.name / "spec" / "S1" / "deeper",
            self.root / self.name / ".." / ".." / "S1",
            self.root / self.name / "spec" / "S1 " / str(victim),  # an extra argument
            f"{self.root}/{self.name}/spec/S1 {victim}",
        ):
            with self.subTest(scratch=scratch):
                code, out = self.prepare(scratch, "none", "none")
                self.assertEqual(code, 2, out)
        self.assertTrue(victim.is_dir())

    def test_refuses_a_symlink_out_of_the_root(self):
        outside = self.tmp / "outside"
        (outside / "spec" / "S1").mkdir(parents=True)
        (outside / "spec" / "S1" / "keep.txt").write_text("keep\n")
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / self.name).symlink_to(outside)
        self.addCleanup((self.root / self.name).unlink)
        code, out = self.prepare(self.root / self.name / "spec" / "S1", "none", "none")
        self.assertEqual(code, 2, out)
        self.assertIn("outside", out)
        self.assertTrue((outside / "spec" / "S1" / "keep.txt").exists())

    def test_refuses_bad_read_at_and_repo(self):
        for repo, read_at in (
            (self.repo, "HEAD"),  # not a hash: could be an option or a ref
            (self.repo, "--output=/tmp/x"),
            (self.repo, "abcdef0"),  # a hash that isn't a commit here
            (self.tmp, self.sha),  # not a git repo
            (self.repo, "none"),  # read-at none needs repo none
        ):
            with self.subTest(repo=repo, read_at=read_at):
                code, out = self.prepare(self.scratch, repo, read_at)
                self.assertEqual(code, 2, out)
        self.assertFalse(self.scratch.exists())

    def test_wrong_argument_count(self):
        self.assertEqual(self.prepare(self.scratch)[0], 2)


if __name__ == "__main__":
    unittest.main()
