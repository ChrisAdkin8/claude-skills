"""Tests for skills/implement/scripts/prepare-verify.sh and run-verify.sh: the implement-verifier's
scratch export, and its launcher.

prepare-verify.sh deletes and fills only a verification's own scratch directory under
~/.cache/implement-verify: the head in src/, diff.patch, and each work item's starting state in
before/W<n>/. run-verify.sh launches claude only there; a stub `claude` first on PATH records its
arguments and prints a result, so nothing is sent to a model. Both run under a home of their own.

Run with: python3 -m unittest discover -s tests
"""

import filecmp
import json
import os
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "implement" / "scripts"
PREPARE = SCRIPTS / "prepare-verify.sh"
RUN = SCRIPTS / "run-verify.sh"
STUB = """#!/usr/bin/env python3
import json, os, sys
with open(os.environ["STUB_CALLS"], "a") as f:
    f.write(json.dumps({"argv": sys.argv[1:], "cwd": os.getcwd(),
                        "uv": os.environ.get("UV_CACHE_DIR")}) + "\\n")
reply = os.environ.get("STUB_REPLY", "| W | Done when |\\nVerified: 1 of 1\\nImplementation holds: yes")
print(json.dumps({"result": reply, "subtype": "success", "total_cost_usd": 0.01}))
"""


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@local", "-c", "user.name=t", *args],
        capture_output=True, text=True, check=True,
    ).stdout  # fmt: skip


def commit(repo, files, message):
    for rel, text in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text)
    git(repo, "add", ".")
    git(repo, "commit", "-qm", message)
    return git(repo, "rev-parse", "HEAD").strip()


def same_tree(a, b):
    """True if directories a and b hold the same files with the same contents."""
    cmp = filecmp.dircmp(a, b)
    if cmp.left_only or cmp.right_only or cmp.funny_files:
        return False
    _, mismatch, errors = filecmp.cmpfiles(a, b, cmp.common_files, shallow=False)
    if mismatch or errors:
        return False
    return all(same_tree(Path(a) / d, Path(b) / d) for d in cmp.common_dirs)


class Home(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()
        # A home of its own, so the scripts' `rm -rf` never runs in the real ~/.cache.
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.root = self.home / ".cache" / "implement-verify"
        self.name = f"test-{uuid.uuid4().hex[:8]}"
        self.scratch = self.root / self.name / "spec" / "V1"
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        (bin_dir / "claude").write_text(STUB)
        (bin_dir / "claude").chmod(0o755)
        self.calls = self.tmp / "calls.jsonl"
        self.env = {
            **os.environ,
            "HOME": str(self.home),
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "STUB_CALLS": str(self.calls),
        }
        self.env.pop("RUN_AGENT_MODEL", None)

    def run_script(self, script, *args, env=None):
        run = subprocess.run(
            [str(script), *map(str, args)], capture_output=True, text=True, check=False,
            env=env or self.env,
        )  # fmt: skip
        return run.returncode, run.stdout + run.stderr


class PrepareVerify(Home):
    def setUp(self):
        super().setUp()
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        self.base = commit(
            self.repo, {"a.txt": "base\n", "b.txt": "b\n"}, "spec: in progress"
        )
        self.w1 = commit(self.repo, {"a.txt": "w1\n"}, "spec: do the first thing (W1)")
        self.other = commit(self.repo, {"c.txt": "c\n"}, "readme: an aside")
        self.w2 = commit(self.repo, {"b.txt": "w2\n"}, "repo: do the second thing (W2)")
        (self.repo / "a.txt").write_text("uncommitted\n")  # never exported

    def prepare(self, scratch=None, base=None, head=None):
        return self.run_script(
            PREPARE,
            scratch or self.scratch,
            self.repo,
            base or self.base,
            head or self.w2,
        )

    def archive(self, rev):
        out = self.tmp / f"archive-{rev[:8]}"
        out.mkdir()
        subprocess.run(
            f"git -C '{self.repo}' archive {rev} | tar -x -C '{out}'",
            shell=True,
            check=True,
        )
        return out

    def test_exports_head_and_its_diff(self):
        (self.scratch / "src").mkdir(parents=True)
        (self.scratch / "old.txt").write_text("from an earlier run\n")
        code, out = self.prepare()
        self.assertEqual(code, 0, out)
        self.assertTrue(same_tree(self.scratch / "src", self.archive(self.w2)))
        self.assertEqual((self.scratch / "src" / "a.txt").read_text(), "w1\n")
        self.assertFalse((self.scratch / "src" / ".git").exists())
        self.assertFalse((self.scratch / "old.txt").exists())
        self.assertEqual(
            (self.scratch / "diff.patch").read_text(),
            git(self.repo, "diff", self.base, self.w2),
        )

    def test_exports_each_work_items_starting_state(self):
        code, out = self.prepare()
        self.assertEqual(code, 0, out)
        before = self.scratch / "before"
        self.assertEqual(sorted(p.name for p in before.iterdir()), ["W1", "W2"])
        self.assertTrue(same_tree(before / "W1", self.archive(self.base)))
        self.assertTrue(same_tree(before / "W2", self.archive(self.other)))

    def test_refuses_paths_outside_its_scratch_layout(self):
        victim = self.tmp / "victim"
        victim.mkdir()
        for scratch in (
            victim,  # anywhere else
            self.root / self.name / "V1",  # a level missing
            self.root / self.name / "spec" / "V1" / "deeper",
            self.root
            / self.name
            / "spec"
            / "S1",  # a spike's name, not a verification's
            self.root / self.name / ".." / ".." / "V1",
            self.root / self.name / "spec" / ".." / "V1",
            f"{self.root}/{self.name}/spec/V1 {victim}",
            self.home / ".cache" / "spec-spikes" / self.name / "spec" / "V1",
        ):
            with self.subTest(scratch=scratch):
                code, out = self.prepare(scratch)
                self.assertEqual(code, 2, out)
        self.assertTrue(victim.is_dir())

    def test_refuses_a_symlinked_parent(self):
        outside = self.tmp / "outside"
        (outside / "spec" / "V1").mkdir(parents=True)
        (outside / "spec" / "V1" / "keep.txt").write_text("keep\n")
        self.root.mkdir(parents=True)
        (self.root / self.name).symlink_to(outside)
        code, out = self.prepare()
        self.assertEqual(code, 2, out)
        self.assertIn("outside", out)
        self.assertTrue((outside / "spec" / "V1" / "keep.txt").exists())

    def test_refuses_a_symlinked_scratch(self):
        outside = self.tmp / "outside"
        outside.mkdir()
        (outside / "keep.txt").write_text("keep\n")
        self.scratch.parent.mkdir(parents=True)
        self.scratch.symlink_to(outside)
        code, out = self.prepare()
        self.assertEqual(code, 2, out)
        self.assertTrue((outside / "keep.txt").exists())

    def test_refuses_bad_revs_and_repos(self):
        for base, head in (
            ("--output=/tmp/x", self.w2),
            (self.base, "-p"),
            ("abcdef0", self.w2),  # not a commit here
        ):
            with self.subTest(base=base, head=head):
                code, out = self.prepare(base=base, head=head)
                self.assertEqual(code, 2, out)
        code, out = self.run_script(PREPARE, self.scratch, self.tmp, self.base, self.w2)
        self.assertEqual(code, 2, out)
        self.assertFalse(self.scratch.exists())

    def test_wrong_argument_count(self):
        self.assertEqual(self.run_script(PREPARE, self.scratch)[0], 2)


class RunVerify(Home):
    def make_scratch(self, files=("brief.md", "spec.md", "diff.patch")):
        (self.scratch / "src").mkdir(parents=True, exist_ok=True)
        for name in files:
            (self.scratch / name).write_text(
                "the brief\n" if name == "brief.md" else "x\n"
            )
        return self.scratch

    def calls_made(self):
        if not self.calls.exists():
            return []
        return [json.loads(line) for line in self.calls.read_text().splitlines()]

    def test_refuses_a_path_outside_its_root_whether_or_not_it_exists(self):
        made = self.tmp / "x"
        made.mkdir()
        for path in ("/tmp/x", made, self.tmp / "missing"):
            with self.subTest(path=path):
                code, out = self.run_script(RUN, path)
                self.assertEqual(code, 2, out)
                self.assertIn("not under ~/.cache/implement-verify/", out)
        self.assertEqual(self.calls_made(), [])

    def test_refuses_other_layouts_and_missing_files(self):
        self.make_scratch()
        for path in (
            self.root,
            self.root / self.name / "spec",
            self.root / self.name / "spec" / "V1" / "src",
            self.root / self.name / "spec" / ".." / "spec" / "V1",
            self.root / self.name / "spec" / "V2",  # missing
        ):
            with self.subTest(path=path):
                code, out = self.run_script(RUN, path)
                self.assertEqual(code, 2, out)
        (self.scratch / "spec.md").unlink()
        code, out = self.run_script(RUN, self.scratch)
        self.assertEqual(code, 2, out)
        self.assertIn("missing", out)
        self.assertEqual(self.calls_made(), [])

    def test_refuses_a_symlink_out_of_the_root(self):
        outside = self.tmp / "outside"
        (outside / "spec" / "V1" / "src").mkdir(parents=True)
        for name in ("brief.md", "spec.md", "diff.patch"):
            (outside / "spec" / "V1" / name).write_text("x\n")
        self.root.mkdir(parents=True)
        (self.root / self.name).symlink_to(outside)
        code, out = self.run_script(RUN, self.scratch)
        self.assertEqual(code, 2, out)
        self.assertEqual(self.calls_made(), [])

    def test_runs_in_scratch_with_verify_settings_and_prompt(self):
        self.make_scratch()
        code, out = self.run_script(RUN, self.scratch)
        self.assertEqual(code, 0, out)
        (call,) = self.calls_made()
        argv = call["argv"]
        flag = lambda name: argv[argv.index(name) + 1]
        self.assertEqual(Path(call["cwd"]).resolve(), self.scratch.resolve())
        self.assertEqual(
            flag("--settings"), str(SCRIPTS.parent / "verify-settings.json")
        )
        self.assertEqual(
            flag("--append-system-prompt-file"), str(SCRIPTS.parent / "verifier.md")
        )
        self.assertTrue((SCRIPTS.parent / "verifier.md").is_file())
        self.assertEqual(flag("--max-budget-usd"), "5")
        self.assertEqual(flag("--max-turns"), "100")
        self.assertEqual(flag("--setting-sources"), "user")
        self.assertEqual(
            flag("--allowedTools"), "Read Grep Glob Bash Write(./**) Edit(./**)"
        )
        self.assertIn("--strict-mcp-config", argv)
        self.assertEqual(argv[-1], "the brief")
        self.assertTrue(call["uv"].endswith("/.cache/spec-spikes/.uv-cache"))
        self.assertIn(
            "Implementation holds: yes", (self.scratch / "reply.md").read_text()
        )
        self.assertIn("total_cost_usd", (self.scratch / "run.json").read_text())

    def test_model_only_when_run_agent_model_is_set(self):
        self.make_scratch()
        self.run_script(RUN, self.scratch)
        self.run_script(RUN, self.scratch, env={**self.env, "RUN_AGENT_MODEL": "opus"})
        without, with_model = (c["argv"] for c in self.calls_made())
        self.assertNotIn("--model", without)
        self.assertEqual(with_model[with_model.index("--model") + 1], "opus")

    def test_a_reply_without_its_closing_lines_exits_3(self):
        self.make_scratch()
        for reply in (
            "Request timed out",
            "| W | Done when |\nVerified: 1 of 1",  # no Implementation holds
            "| W | Done when |\nImplementation holds: yes",  # no Verified
            "Verified: one of two\nImplementation holds: maybe",
        ):
            with self.subTest(reply=reply):
                code, out = self.run_script(
                    RUN, self.scratch, env={**self.env, "STUB_REPLY": reply}
                )
                self.assertEqual(code, 3, out)
                self.assertIn("reply.md", out)
                self.assertEqual((self.scratch / "reply.md").read_text(), reply + "\n")


if __name__ == "__main__":
    unittest.main()
