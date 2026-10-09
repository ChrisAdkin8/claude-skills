"""Tests for skills/spec/scripts/prepare-spike.sh: it deletes and fills only a spike's own scratch
directory under ~/.cache/spec-spikes, whatever arguments it's given, and exports the repo as git
stores it, whatever the repo's attributes say.

Run with: python3 -m unittest discover -s ~/code/github.com/claude-skills/tests
"""

import os
import shlex
import stat
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "spec"
    / "scripts"
    / "prepare-spike.sh"
)


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def committed(repo, rev):
    """{path: (mode, bytes)} for each file in rev's tree, as git stores it, before any attribute
    or filter: a link's bytes are its target."""
    tree = subprocess.run(
        ["git", "-C", str(repo), "ls-tree", "-r", "-z", rev],
        capture_output=True,
        check=True,
    ).stdout
    files = {}
    for entry in filter(None, tree.split(b"\0")):
        meta, path = entry.split(b"\t", 1)
        mode, _, oid = meta.decode().split()
        blob = subprocess.run(
            ["git", "-C", str(repo), "cat-file", "blob", oid],
            capture_output=True,
            check=True,
        ).stdout
        files[path.decode()] = (mode, blob)
    return files


def exported(root):
    """The same map for a directory, in git's modes: a link is 120000 and its target, an
    executable file 100755, any other file 100644."""
    files = {}
    for top, dirs, names in os.walk(root):
        for name in dirs + names:
            path = Path(top) / name
            rel = path.relative_to(root).as_posix()
            if path.is_symlink():
                files[rel] = ("120000", os.fsencode(os.readlink(path)))
            elif path.is_file():
                executable = path.stat().st_mode & stat.S_IXUSR
                files[rel] = ("100755" if executable else "100644", path.read_bytes())
    return files


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

    def test_a_bad_name_is_named_with_the_rule(self):
        for repo_dir, spec in (("My App", "spec"), (self.name, "café")):
            with self.subTest(repo_dir=repo_dir, spec=spec):
                bad = spec if repo_dir == self.name else repo_dir
                code, out = self.prepare(self.root / repo_dir / spec / "S1", self.repo, self.sha)
                self.assertEqual(code, 2, out)
                self.assertIn(f'"{bad}"', out)
                self.assertIn("may hold only letters, digits", out)
                self.assertIn("starting with a letter or digit", out)

    def test_exports_the_repo_at_read_at(self):
        (self.scratch / "src").mkdir(parents=True)
        (self.scratch / "old.txt").write_text("from an earlier run\n")
        code, out = self.prepare(self.scratch, self.repo, self.sha)
        self.assertEqual(code, 0, out)
        self.assertEqual((self.scratch / "src" / "a.txt").read_text(), "at read-at\n")
        self.assertFalse((self.scratch / "old.txt").exists())

    def test_exports_the_committed_bytes_whatever_the_attributes_say(self):
        # `git archive` would leave tests/ out, rewrite VERSION and run the filter, whose smudge
        # is set up after the commit, as a repo's own .git/config could hold it.
        repo = self.repo
        (repo / ".gitattributes").write_text(
            "tests/** export-ignore\nVERSION export-subst\n*.txt filter=probe\n"
        )
        (repo / "VERSION").write_text("$Format:%H$\n")
        (repo / "tests").mkdir()
        (repo / "tests" / "test_a.py").write_text("assert True\n")
        (repo / "run.sh").write_text("#!/bin/sh\necho run\n")
        (repo / "run.sh").chmod(0o755)
        (repo / "link").symlink_to("a.txt")
        git(repo, "add", ".gitattributes", "VERSION", "tests", "run.sh", "link")
        git(
            repo,
            "-c", "user.email=t@local", "-c", "user.name=t",
            "commit", "-qm", "two",
        )  # fmt: skip
        sha = git(repo, "rev-parse", "--short", "HEAD")
        ran = self.tmp / "ran"
        git(
            repo,
            "config",
            "filter.probe.smudge",
            f"echo smudge >> {shlex.quote(str(ran))}; cat",
        )
        code, out = self.prepare(self.scratch, repo, sha)
        self.assertEqual(code, 0, out)
        src = self.scratch / "src"
        self.assertTrue((src / "tests" / "test_a.py").is_file())
        self.assertEqual((src / "VERSION").read_bytes(), b"$Format:%H$\n")
        self.assertTrue(os.access(src / "run.sh", os.X_OK))
        self.assertEqual(os.readlink(src / "link"), "a.txt")
        self.assertEqual(exported(src), committed(repo, sha))
        self.assertFalse(ran.exists(), ran.exists() and ran.read_text())

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
