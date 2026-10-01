"""Tests for skills/implement/scripts/scan-diff.py: out-of-scope files and weakened tests in a
staged diff.

Run with: python3 -m unittest discover -s tests
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "implement" / "scripts" / "scan-diff.py"


def diff(path, hunks, header=""):
    """A one-file unified diff of `path`: its git header, then the hunks as given."""
    old = "/dev/null" if "new file mode" in header else f"a/{path}"
    new = "/dev/null" if "deleted file mode" in header else f"b/{path}"
    return (
        f"diff --git a/{path} b/{path}\n{header}index 1111111..2222222\n"
        f"--- {old}\n+++ {new}\n{hunks}"
    )


# One fixture per kind. Each lists the files it may touch, so only its own kind is flagged.
KINDS = {
    "scope": (
        diff("src/app.py", "@@ -1,1 +1,1 @@\n-x = 1\n+x = 2\n"),
        [],
        "FLAG scope: src/app.py:0: not in --files",
    ),
    "deleted-test": (
        diff(
            "tests/test_app.py",
            "@@ -1,4 +1,2 @@\n import app\n-def test_old():\n-    pass\n # end\n",
        ),
        ["tests/test_app.py"],
        "FLAG deleted-test: tests/test_app.py:2: def test_old():",
    ),
    "skip": (
        diff(
            "tests/test_app.py",
            "@@ -3,1 +3,2 @@\n+@skip('flaky')\n def test_x():\n",
        ),
        ["tests/test_app.py"],
        "FLAG skip: tests/test_app.py:3: @skip('flaky')",
    ),
    "silenced": (
        diff("src/app.py", "@@ -1,1 +1,1 @@\n-import os\n+import os  # noqa\n"),
        ["src/app.py"],
        "FLAG silenced: src/app.py:1: import os  # noqa",
    ),
    "loosened": (
        diff(
            "tests/test_app.py",
            "@@ -4,2 +4,1 @@\n     x = app.run()\n-    self.assertEqual(x, 3)\n",
        ),
        ["tests/test_app.py"],
        "FLAG loosened: tests/test_app.py:5: self.assertEqual(x, 3)",
    ),
    "mocked": (
        diff(
            "tests/test_app.py",
            "@@ -1,1 +1,2 @@\n import app\n+from unittest.mock import MagicMock\n",
        ),
        ["tests/test_app.py"],
        "FLAG mocked: tests/test_app.py:2: from unittest.mock import MagicMock",
    ),
}


def scan(args, cwd=None, env=None):
    run = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, check=False, cwd=cwd, env=env,
    )  # fmt: skip
    return run.returncode, run.stdout, run.stderr


class Kinds(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def scan_text(self, text, files):
        path = self.tmp / "change.diff"
        path.write_text(text)
        return scan(["--diff-file", str(path), "--files", *files])

    def test_each_kind_gives_exactly_its_flag(self):
        for kind, (text, files, expected) in KINDS.items():
            with self.subTest(kind=kind):
                code, out, err = self.scan_text(text, files)
                self.assertEqual(out.splitlines(), [expected], err)
                self.assertEqual(code, 1)

    def test_a_deleted_test_file_is_flagged(self):
        text = diff(
            "tests/test_gone.py",
            "@@ -1,2 +0,0 @@\n-def test_a():\n-    pass\n",
            header="deleted file mode 100644\n",
        )
        code, out, _ = self.scan_text(text, ["tests/test_gone.py"])
        self.assertIn("FLAG deleted-test: tests/test_gone.py:0: test file deleted", out)
        self.assertEqual(code, 1)

    def test_a_clean_diff_exits_0_with_no_output(self):
        text = diff("src/app.py", "@@ -1,1 +1,2 @@\n x = 1\n+y = 2\n") + diff(
            "tests/test_app.py",
            "@@ -2,1 +2,3 @@\n def test_x():\n+    assert app.y == 2\n+\n",
        )
        code, out, err = self.scan_text(text, ["src/app.py", "tests/test_app.py"])
        self.assertEqual((code, out, err), (0, "", ""))

    def test_scope_flag_clears_when_its_file_is_allowed(self):
        text = diff("src/app.py", "@@ -1,1 +1,1 @@\n-x = 1\n+x = 2\n") + diff(
            "docs/extra.md", "@@ -1,1 +1,1 @@\n-a\n+b\n"
        )
        code, out, _ = self.scan_text(text, ["src/app.py"])
        self.assertEqual(
            out.splitlines(), ["FLAG scope: docs/extra.md:0: not in --files"]
        )
        self.assertEqual(code, 1)
        code, out, _ = self.scan_text(text, ["src/app.py", "docs/extra.md"])
        self.assertEqual((code, out), (0, ""))

    def test_a_changed_test_signature_is_not_a_deleted_test(self):
        text = diff(
            "tests/test_app.py",
            "@@ -1,1 +1,1 @@\n-def test_x(self):\n+def test_x(self, tmp):\n",
        )
        code, out, _ = self.scan_text(text, ["tests/test_app.py"])
        self.assertEqual((code, out), (0, ""))

    def test_test_file_names(self):
        # loosened and mocked only count in a test file.
        hunk = "@@ -1,2 +1,2 @@\n-expect(x).toBe(1)\n+jest.mock('x')\n"
        for path in (
            "__tests__/a.js",
            "src/a.test.js",
            "src/a.spec.ts",
            "pkg/a_test.go",
            "test/a.js",
            "src/test_a.py",
        ):
            with self.subTest(path=path):
                _, out, _ = self.scan_text(diff(path, hunk), [path])
                self.assertIn("FLAG loosened:", out)
                self.assertIn("FLAG mocked:", out)
        code, out, _ = self.scan_text(diff("src/a.js", hunk), ["src/a.js"])
        self.assertEqual((code, out), (0, ""))


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        capture_output=True, text=True, check=True,
    ).stdout.strip()  # fmt: skip


def write(repo, files):
    """Write each {path: text} under `repo`; a text of None deletes the file."""
    for path, text in files.items():
        file = repo / path
        if text is None:
            file.unlink()
        else:
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(text)


class StagedChanges(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def commit(self, files):
        """A new throwaway repo with `files` committed, and that commit's SHA."""
        repo = Path(tempfile.mkdtemp(dir=self.tmp))
        git(repo, "init", "-q")
        write(repo, files)
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "--allow-empty", "-m", "base")
        return repo, git(repo, "rev-parse", "HEAD")

    def scan_staged(self, before, after, files=None):
        """Commit `before`, write `after` over it and stage that, then scan it with --base.
        --files is every path named, unless given."""
        repo, base = self.commit(before)
        write(repo, after)
        git(repo, "add", "-A")
        files = list({**before, **after}) if files is None else files
        return scan(["--base", base, "--files", *files], cwd=repo)

    def test_a_base_that_starts_with_a_dash_never_reaches_git(self):
        # --base=--output=FILE made git diff write the staged diff over FILE. The scan then read
        # nothing and exited 0, which reads as clean.
        repo, _ = self.commit({"app.py": "x = 1\n"})
        write(repo, {"app.py": "x = 2  # noqa\n"})
        git(repo, "add", "-A")
        victim = self.tmp / "victim.txt"
        victim.write_text("keep me\n")
        code, out, err = scan([f"--base=--output={victim}"], cwd=repo)
        self.assertEqual((code, out), (2, ""), err)
        self.assertIn("not a revision", err)
        self.assertEqual(victim.read_text(), "keep me\n")

    def test_base_must_name_a_commit(self):
        repo, base = self.commit({"app.py": "x = 1\n"})
        write(repo, {"app.py": "x = 2  # noqa\n"})
        git(repo, "add", "-A")
        tree = git(repo, "rev-parse", "HEAD^{tree}")
        for rev in (tree, "no-such-rev", "HEAD..HEAD"):
            with self.subTest(rev=rev):
                code, out, err = scan(["--base", rev], cwd=repo)
                self.assertEqual((code, out), (2, ""), err)
                self.assertIn("is not a commit", err)
        # Any name for a commit still works.
        for rev in (base, base[:12], "HEAD", "HEAD~0"):
            with self.subTest(rev=rev):
                code, out, err = scan(["--base", rev], cwd=repo)
                self.assertEqual(
                    (code, out), (1, "FLAG silenced: app.py:1: x = 2  # noqa\n"), err
                )

    def test_base_reads_staged_changes_including_a_new_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init", "-q")
            (repo / "app.py").write_text("x = 1\n")
            git(repo, "add", ".")
            git(repo, "commit", "-qm", "init")
            base = git(repo, "rev-parse", "HEAD")
            (repo / "app.py").write_text("x = 2  # noqa\n")
            (repo / "new.py").write_text("y = 1\n")
            (repo / "unstaged.py").write_text("z = 1\n")  # never staged, so never seen
            git(repo, "add", "app.py", "new.py")
            code, out, err = scan(["--base", base, "--files", "app.py"], cwd=repo)
            self.assertEqual(
                out.splitlines(),
                [
                    "FLAG silenced: app.py:1: x = 2  # noqa",
                    "FLAG scope: new.py:0: not in --files",
                ],
                err,
            )
            self.assertEqual(code, 1)
            code, out, _ = scan(
                ["--base", base, "--files", "app.py", "new.py"], cwd=repo
            )
            self.assertEqual(
                out.splitlines(), ["FLAG silenced: app.py:1: x = 2  # noqa"]
            )


if __name__ == "__main__":
    unittest.main()
