"""Tests for skills/implement/scripts/run-implementer.sh: the launcher /implement runs the
implementer with. It refuses a working directory that isn't a git worktree of a repo under
~/code, builds the `claude -p --agents ... --agent implementer` command, checks the reply's closing
`Implementer:` line, and keeps the whole run, resumes included, under one cap.

A stub `claude` first on PATH records its arguments and prints a result, so nothing is sent to a
model. Everything runs under a home of its own.
Run with: python3 -m unittest discover -s tests
"""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "skills" / "implement" / "scripts" / "run-implementer.sh"
STUB = """#!/usr/bin/env python3
import json, os, sys
calls = os.environ["STUB_CALLS"]
with open(calls, "a") as f:
    f.write(json.dumps({"argv": sys.argv[1:], "cwd": os.getcwd(),
                        "root": os.environ.get("CLAUDE_PLUGIN_ROOT")}) + "\\n")
n = sum(1 for _ in open(calls))
tail = os.environ.get("STUB_TAIL", "Implementer: done")
print(json.dumps({"session_id": "sess-1", "result": f"reply {n}\\n{tail}", "subtype": "success",
                  "total_cost_usd": float(os.environ.get("STUB_COST", "0.5"))}))
"""


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@local", "-c", "user.name=t", *args],
        capture_output=True, text=True, check=True,
    ).stdout  # fmt: skip


class RunImplementer(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        (bin_dir / "claude").write_text(STUB)
        (bin_dir / "claude").chmod(0o755)
        self.calls = self.tmp / "calls.jsonl"
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.env = {
            **os.environ,
            "HOME": str(self.home),
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "STUB_CALLS": str(self.calls),
        }
        for var in ("RUN_AGENT_MODEL", "IMPLEMENT_MAX_USD"):
            self.env.pop(var, None)
        # A repo under ~/code, and the worktree /implement would add beside it.
        self.repo = self.home / "code" / "proj"
        self.repo.mkdir(parents=True)
        git(self.repo, "init", "-q")
        (self.repo / "a.txt").write_text("a\n")
        git(self.repo, "add", "a.txt")
        git(self.repo, "commit", "-qm", "base")
        self.worktree = self.home / "code" / "proj-worktrees" / "spec"
        git(
            self.repo,
            "worktree",
            "add",
            "-q",
            str(self.worktree),
            "-b",
            "implement/spec",
        )
        self.run_dir = (
            self.home / ".cache" / "implement-runs" / "proj--spec" / "implementer"
        )

    def brief(self, text="Implement it.\n"):
        self.run_dir.mkdir(parents=True, exist_ok=True)
        (self.run_dir / "brief.md").write_text(text)

    def launch(self, *args):
        run = subprocess.run(
            [str(SCRIPT), *map(str, args)],
            capture_output=True,
            text=True,
            env=self.env,
            check=False,
        )
        return run.returncode, run.stdout + run.stderr

    def calls_made(self):
        return (
            [json.loads(line) for line in self.calls.read_text().splitlines()]
            if self.calls.exists()
            else []
        )

    def flag(self, argv, name):
        return argv[argv.index(name) + 1] if name in argv else None

    def test_is_executable(self):
        self.assertTrue(os.access(SCRIPT, os.X_OK))

    def test_refuses_a_directory_outside_code_or_not_a_worktree(self):
        self.brief()
        # A worktree of a repo outside ~/code.
        outside = self.tmp / "elsewhere" / "proj"
        outside.mkdir(parents=True)
        git(outside, "init", "-q")
        (outside / "a.txt").write_text("a\n")
        git(outside, "add", "a.txt")
        git(outside, "commit", "-qm", "base")
        outside_wt = self.tmp / "elsewhere" / "wt"
        git(outside, "worktree", "add", "-q", str(outside_wt), "-b", "implement/spec")
        plain = self.home / "code" / "plain"
        plain.mkdir()
        for work in (
            outside_wt,  # a worktree, but not under ~/code
            plain,  # under ~/code, not a git repo
            self.repo,  # the repo's own checkout, not a worktree of it
            self.home / "code" / "missing",
        ):
            with self.subTest(work=work):
                code, out = self.launch(work, self.run_dir)
                self.assertEqual(code, 2, out)
        self.assertEqual(self.calls_made(), [])

    def test_refuses_other_run_dirs_and_options(self):
        self.brief()
        root = self.home / ".cache" / "implement-runs"
        for args in (
            (self.worktree, self.tmp / "elsewhere"),
            (self.worktree, root / "proj--spec"),  # one level short
            (self.worktree, root / "proj--spec" / ".." / "x" / "y"),
            (self.worktree, self.run_dir, "--force"),
            (self.worktree,),
        ):
            with self.subTest(args=args):
                code, out = self.launch(*args)
                self.assertEqual(code, 2, out)
        self.assertEqual(self.calls_made(), [])

    def test_needs_a_brief(self):
        code, out = self.launch(self.worktree, self.run_dir)
        self.assertEqual(code, 2, out)
        self.assertIn("brief.md", out)

    def test_builds_the_implementer_command(self):
        self.brief()
        code, out = self.launch(self.worktree, self.run_dir)
        self.assertEqual(code, 0, out)
        (call,) = self.calls_made()
        argv = call["argv"]
        self.assertEqual(argv[:1], ["-p"])
        self.assertEqual(self.flag(argv, "--agent"), "implementer")
        agents = Path(self.flag(argv, "--agents"))
        self.assertEqual(agents, self.run_dir / "agents.json")
        defs = json.loads(agents.read_text())
        self.assertEqual(list(defs), ["implementer"])
        self.assertNotIn("hooks", defs["implementer"])
        self.assertNotIn("${", defs["implementer"]["prompt"])
        self.assertEqual(
            defs["implementer"]["tools"],
            ["Read", "Edit", "Write", "Glob", "Grep", "Bash", "Skill"],
        )
        self.assertEqual(
            self.flag(argv, "--allowedTools"), "Read,Edit,Write,Glob,Grep,Bash,Skill"
        )
        # The repo's own settings and CLAUDE.md load; edits are accepted; no OS sandbox is set.
        self.assertEqual(self.flag(argv, "--setting-sources"), "user,project")
        self.assertEqual(self.flag(argv, "--permission-mode"), "acceptEdits")
        self.assertNotIn("--settings", argv)
        self.assertEqual(self.flag(argv, "--max-budget-usd"), "20")
        self.assertEqual(self.flag(argv, "--output-format"), "json")
        self.assertNotIn("--resume", argv)
        self.assertNotIn("--model", argv)
        self.assertEqual(argv[-1], "Implement it.")
        self.assertEqual(Path(call["cwd"]).resolve(), self.worktree.resolve())
        self.assertEqual(call["root"], str(REPO))
        self.assertTrue((self.run_dir / "reply.md").read_text().startswith("reply 1\n"))
        self.assertEqual((self.run_dir / "session_id").read_text(), "sess-1")
        self.assertTrue((self.run_dir / "run.json").exists())
        self.assertTrue((self.run_dir / "run-1.json").exists())

    def test_cap_and_model_from_the_environment(self):
        self.brief()
        self.env["IMPLEMENT_MAX_USD"] = "5"
        self.env["RUN_AGENT_MODEL"] = "sonnet"
        code, out = self.launch(self.worktree, self.run_dir)
        self.assertEqual(code, 0, out)
        (call,) = self.calls_made()
        self.assertEqual(self.flag(call["argv"], "--max-budget-usd"), "5")
        self.assertEqual(self.flag(call["argv"], "--model"), "sonnet")

    def test_reply_without_an_implementer_line_exits_3(self):
        self.brief()
        for tail in (
            "All done, I think.",
            "Implementer: done\nand one more thing",
            "Implementer: question:",
            "Implementer: finished",
        ):
            with self.subTest(tail=tail):
                self.env["STUB_TAIL"] = tail
                code, out = self.launch(self.worktree, self.run_dir)
                self.assertEqual(code, 3, out)
        for tail in (
            "Implementer: done",
            "Implementer: question: W1's test conflicts; change it?",
            "Implementer: stopped: a third failed attempt at W2\n",
        ):
            with self.subTest(tail=tail):
                self.env["STUB_TAIL"] = tail
                code, out = self.launch(self.worktree, self.run_dir)
                self.assertEqual(code, 0, out)

    def test_resume_gets_the_cap_less_what_was_spent(self):
        self.brief()
        self.env["IMPLEMENT_MAX_USD"] = "10"
        self.env["STUB_COST"] = "2.5"
        code, out = self.launch(self.worktree, self.run_dir)
        self.assertEqual(code, 0, out)
        (self.run_dir / "followup.md").write_text("The user says yes.\n")
        self.env["STUB_COST"] = "4"
        code, out = self.launch(self.worktree, self.run_dir, "--resume")
        self.assertEqual(code, 0, out)
        code, out = self.launch(self.worktree, self.run_dir, "--resume")
        self.assertEqual(code, 0, out)
        first, second, third = (c["argv"] for c in self.calls_made())
        self.assertEqual(self.flag(first, "--max-budget-usd"), "10")
        self.assertEqual(self.flag(second, "--max-budget-usd"), "7.5")
        self.assertEqual(self.flag(third, "--max-budget-usd"), "3.5")
        self.assertEqual(self.flag(second, "--resume"), "sess-1")
        self.assertEqual(second[-1], "The user says yes.")
        # Every call's result is kept, and every earlier reply.
        for n in (1, 2, 3):
            self.assertTrue((self.run_dir / f"run-{n}.json").exists(), n)
        self.assertTrue(
            (self.run_dir / "reply-1.md").read_text().startswith("reply 1\n")
        )
        self.assertTrue((self.run_dir / "reply.md").read_text().startswith("reply 3\n"))

    def test_resume_refused_once_the_cap_is_spent(self):
        self.brief()
        self.env["IMPLEMENT_MAX_USD"] = "5"
        self.env["STUB_COST"] = "3"
        self.assertEqual(self.launch(self.worktree, self.run_dir)[0], 0)
        (self.run_dir / "followup.md").write_text("Carry on.\n")
        self.assertEqual(self.launch(self.worktree, self.run_dir, "--resume")[0], 0)
        code, out = self.launch(self.worktree, self.run_dir, "--resume")
        self.assertEqual(code, 2, out)
        self.assertIn("cap", out)
        self.assertEqual(len(self.calls_made()), 2)

    def test_resume_needs_a_session_and_a_followup(self):
        self.brief()
        code, out = self.launch(self.worktree, self.run_dir, "--resume")
        self.assertEqual(code, 2, out)
        self.assertEqual(self.launch(self.worktree, self.run_dir)[0], 0)
        code, out = self.launch(self.worktree, self.run_dir, "--resume")
        self.assertEqual(code, 2, out)
        self.assertIn("followup.md", out)

    def test_a_fresh_run_starts_the_count_again(self):
        self.brief()
        self.env["IMPLEMENT_MAX_USD"] = "5"
        self.env["STUB_COST"] = "4"
        self.assertEqual(self.launch(self.worktree, self.run_dir)[0], 0)
        self.assertEqual(self.launch(self.worktree, self.run_dir)[0], 0)
        self.assertFalse((self.run_dir / "run-2.json").exists())
        second = self.calls_made()[1]["argv"]
        self.assertEqual(self.flag(second, "--max-budget-usd"), "5")


if __name__ == "__main__":
    unittest.main()
