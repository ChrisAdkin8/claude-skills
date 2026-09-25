"""Tests for hooks/run-agent.sh: which runs it accepts, what it passes to claude, and how a
follow-up resumes the same session.

A stub `claude` first on PATH records its arguments and prints a result, so nothing is sent to a
model. Run with: python3 -m unittest discover -s ~/code/github.com/claude-skills/tests
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "hooks" / "run-agent.sh"
ROOT = Path.home() / ".cache" / "agent-runs"
STUB = """#!/usr/bin/env python3
import json, os, sys
calls = os.environ["STUB_CALLS"]
with open(calls, "a") as f:
    f.write(json.dumps({"argv": sys.argv[1:], "cwd": os.getcwd()}) + "\\n")
n = sum(1 for _ in open(calls))
print(json.dumps({"session_id": "sess-1", "result": f"reply {n}", "subtype": "success"}))
"""


class RunAgent(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        (bin_dir / "claude").write_text(STUB)
        (bin_dir / "claude").chmod(0o755)
        self.calls = self.tmp / "calls.jsonl"
        self.env = {
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "STUB_CALLS": str(self.calls), "RUN_AGENT_LOG": str(self.tmp / "sessions.log"),
        }
        self.name = f"test-{uuid.uuid4().hex[:8]}"
        self.addCleanup(shutil.rmtree, ROOT / self.name, True)
        self.work = self.tmp / "work"
        self.work.mkdir()

    def run_agent(self, *args):
        run = subprocess.run(
            [str(SCRIPT), *map(str, args)],
            capture_output=True,
            text=True,
            env=self.env,
            check=False,
        )
        return run.returncode, run.stdout + run.stderr

    def run_dir(self, agent="cold-reviewer"):
        return ROOT / self.name / agent

    def calls_made(self):
        return (
            [json.loads(l) for l in self.calls.read_text().splitlines()]
            if self.calls.exists()
            else []
        )

    def test_refuses_other_agents_and_run_dirs(self):
        for args in (
            ("general-purpose", self.work, self.run_dir()),
            ("cold-reviewer", self.work, self.tmp / "elsewhere"),
            ("cold-reviewer", self.work, ROOT / self.name),  # one level short
            ("cold-reviewer", self.work, ROOT / self.name / ".." / "x" / "y"),
            ("cold-reviewer", self.tmp / "missing", self.run_dir()),
            ("cold-reviewer", self.work, self.run_dir(), "--force"),
        ):
            with self.subTest(args=args):
                code, out = self.run_agent(*args)
                self.assertEqual(code, 2, out)
        self.assertEqual(self.calls_made(), [])

    def test_needs_a_brief(self):
        code, out = self.run_agent("cold-reviewer", self.work, self.run_dir())
        self.assertEqual(code, 2)
        self.assertIn("brief.md", out)

    def test_run_passes_agent_sandbox_and_brief(self):
        run = self.run_dir()
        run.mkdir(parents=True)
        (run / "brief.md").write_text("Review this.\n")
        code, out = self.run_agent("cold-reviewer", self.work, run)
        self.assertEqual(code, 0, out)
        (call,) = self.calls_made()
        argv = call["argv"]
        self.assertEqual(argv[argv.index("--agent") + 1], "cold-reviewer")
        self.assertTrue(argv[argv.index("--settings") + 1].endswith("hooks/agent-sandbox.json"))
        self.assertIn("--strict-mcp-config", argv)  # only the researcher keeps MCP servers
        self.assertNotIn("--resume", argv)
        self.assertEqual(argv[-1], "Review this.")
        self.assertEqual(Path(call["cwd"]).resolve(), self.work.resolve())
        self.assertEqual((run / "reply.md").read_text(), "reply 1\n")
        self.assertEqual((run / "session_id").read_text(), "sess-1")
        (entry,) = (self.tmp / "sessions.log").read_text().splitlines()
        self.assertEqual(entry.split()[1:], ["cold-reviewer", "sess-1"])

    def test_researcher_keeps_its_mcp_servers(self):
        run = self.run_dir("researcher")
        run.mkdir(parents=True)
        (run / "brief.md").write_text("Research this.\n")
        self.assertEqual(self.run_agent("researcher", self.work, run)[0], 0)
        self.assertNotIn("--strict-mcp-config", self.calls_made()[0]["argv"])

    def test_resume_sends_followup_to_same_session_and_keeps_old_reply(self):
        run = self.run_dir()
        run.mkdir(parents=True)
        (run / "brief.md").write_text("Review this.\n")
        self.assertEqual(self.run_agent("cold-reviewer", self.work, run)[0], 0)
        code, out = self.run_agent("cold-reviewer", self.work, run, "--resume")
        self.assertEqual(code, 2)  # no followup.md yet
        (run / "followup.md").write_text("Send rows 3 to 5.\n")
        code, out = self.run_agent("cold-reviewer", self.work, run, "--resume")
        self.assertEqual(code, 0, out)
        second = self.calls_made()[-1]["argv"]
        self.assertEqual(second[second.index("--resume") + 1], "sess-1")
        self.assertEqual(second[-1], "Send rows 3 to 5.")
        self.assertEqual((run / "reply-1.md").read_text(), "reply 1\n")
        self.assertEqual((run / "reply.md").read_text(), "reply 2\n")

    def test_resume_needs_a_session(self):
        run = self.run_dir()
        run.mkdir(parents=True)
        (run / "followup.md").write_text("More.\n")
        code, out = self.run_agent("cold-reviewer", self.work, run, "--resume")
        self.assertEqual(code, 2)
        self.assertIn("session_id", out)


if __name__ == "__main__":
    unittest.main()
