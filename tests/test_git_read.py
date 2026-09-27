"""Tests for hooks/git-read.py: it runs read-only git commands, and refuses what agent-guard.py
refuses an agent. The skills pre-approve it, and it runs outside the agent sandbox, so this is
the only check on what it runs.

Run with: python3 -m unittest discover -s ~/code/github.com/claude-skills/tests
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "hooks" / "git-read.py"


class GitRead(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name) / "repo"
        self.repo.mkdir()
        for args in (
            ("init", "-q"),
            ("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q",
             "--allow-empty", "-m", "first"),
        ):  # fmt: skip
            subprocess.run(["git", "-C", str(self.repo), *args], check=True)
        self.out = Path(tmp.name) / "written"

    def git_read(self, *args):
        run = subprocess.run(
            [sys.executable, str(SCRIPT), "-C", str(self.repo), *args],
            capture_output=True,
            text=True,
            check=False,
        )
        return run.returncode, run.stdout + run.stderr

    def test_reads_run(self):
        for args in (
            ("log", "--oneline"),
            ("status", "--short"),
            ("rev-parse", "HEAD"),
        ):
            with self.subTest(args=args):
                code, out = self.git_read(*args)
                self.assertEqual(code, 0, out)
        self.assertIn("first", self.git_read("log", "--oneline")[1])

    def test_refused_like_the_guard(self):
        for args in (
            ("log", f"--output={self.out}"),
            ("diff", "--ext-diff"),
            ("-c", "core.pager=touch x", "log"),
            ("-p", "log"),
            ("--git-dir=/elsewhere", "log"),
            ("commit", "--allow-empty", "-m", "x"),
            ("push",),
            ("config", "user.name", "x"),
        ):
            with self.subTest(args=args):
                code, out = self.git_read(*args)
                self.assertEqual(code, 2, out)
                self.assertIn("Blocked by agent-guard", out)
        self.assertFalse(self.out.exists())
        self.assertEqual(self.git_read("rev-list", "--count", "HEAD")[1].strip(), "1")

    def test_no_arguments_refused(self):
        run = subprocess.run(
            [sys.executable, str(SCRIPT)], capture_output=True, check=False
        )
        self.assertEqual(run.returncode, 2)


if __name__ == "__main__":
    unittest.main()
