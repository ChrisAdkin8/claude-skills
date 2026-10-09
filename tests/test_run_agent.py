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

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "hooks" / "run-agent.sh"
STUB = """#!/usr/bin/env python3
import json, os, sys
# The launchers' version check (hooks/launch-checks.sh), answered before the call is logged.
if sys.argv[1:] == ["--version"]:
    print("2.1.285 (Claude Code)")
    sys.exit(0)
calls = os.environ["STUB_CALLS"]
with open(calls, "a") as f:
    f.write(json.dumps({"argv": sys.argv[1:], "cwd": os.getcwd(),
                        "root": os.environ.get("CLAUDE_PLUGIN_ROOT"),
                        "memory": os.environ.get("CLAUDE_CODE_DISABLE_AUTO_MEMORY")}) + "\\n")
n = sum(1 for _ in open(calls))
tail = os.environ.get("STUB_TAIL", "| # | Kind |\\nCounts: 0 findings\\nCold read: yes")
out = {"session_id": "sess-1", "result": f"reply {n}\\n{tail}", "subtype": "success"}
if "STUB_COST" in os.environ:
    out["total_cost_usd"] = float(os.environ["STUB_COST"])
# STUB_RAW is printed instead of a JSON result; STUB_EXIT is the exit code.
print(os.environ.get("STUB_RAW") or json.dumps(out))
sys.exit(int(os.environ.get("STUB_EXIT", "0")))
"""


class RunAgent(unittest.TestCase):
    script = SCRIPT

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        (bin_dir / "claude").write_text(STUB)
        (bin_dir / "claude").chmod(0o755)
        self.calls = self.tmp / "calls.jsonl"
        # A home of its own, so runs land in no real ~/.cache. It has no agents directory: the
        # script finds the agents in hooks/agents.
        home = self.tmp.resolve() / "home"
        (home / ".claude").mkdir(parents=True)
        self.home = home
        self.root = home / ".cache" / "agent-runs"
        self.env = {
            **os.environ,
            "HOME": str(home),
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "STUB_CALLS": str(self.calls),
            "RUN_AGENT_LOG": str(self.tmp / "sessions.log"),
        }
        # Unset here, so only the script can turn auto memory off.
        for var in ("RUN_AGENT_MODEL", "CLAUDE_CODE_DISABLE_AUTO_MEMORY"):
            self.env.pop(var, None)
        self.name = f"test-{uuid.uuid4().hex[:8]}"
        self.work = self.tmp / "work"
        self.work.mkdir()

    def run_agent(self, *args):
        run = subprocess.run(
            [str(self.script), *map(str, args)],
            capture_output=True,
            text=True,
            env=self.env,
            check=False,
        )
        return run.returncode, run.stdout + run.stderr

    def run_dir(self, agent="cold-reviewer"):
        return self.root / self.name / agent

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
            ("cold-reviewer", self.work, self.root / self.name),  # one level short
            ("cold-reviewer", self.work, self.root / self.name / ".." / "x" / "y"),
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
        # The agent is passed by --agents, not loaded from the user's agents directory, with its own tools
        # pre-approved and its guard hooks in the definition.
        defs = json.loads(Path(argv[argv.index("--agents") + 1]).read_text())
        self.assertEqual(list(defs), ["cold-reviewer"])
        self.assertIn("PreToolUse", defs["cold-reviewer"]["hooks"])
        self.assertEqual(argv[argv.index("--allowedTools") + 1], "Read,Grep,Glob,Bash")
        # The settings are the committed file rendered with the plugin root, in the run dir.
        root = self.script.parents[1]
        settings = Path(argv[argv.index("--settings") + 1])
        self.assertEqual(settings, run / "settings.json")
        text = settings.read_text()
        self.assertNotIn("${", text)
        self.assertIn(f"{root}/skills/research/scripts/repo-health.sh *", text)
        self.assertNotIn("~/.claude/skills", text)
        # The agent's guard hook is the root's own, not a path under ~/.claude.
        (guard,) = {
            h["command"]
            for m in defs["cold-reviewer"]["hooks"]["PreToolUse"]
            for h in m["hooks"]
            if h["command"].endswith(" bash")
        }
        self.assertEqual(guard, f'python3 "{root}/hooks/agent-guard.py" bash')
        self.assertEqual(call["root"], str(root))
        # No auto memory: the work dir's MEMORY.md would reach the agent with no tool call the
        # guard could see.
        self.assertEqual(call["memory"], "1")
        # The plugin root is readable: an agent reads the plugin's own files from it, wherever
        # the plugin lives.
        dirs = argv[argv.index("--add-dir") + 1 :]
        dirs = dirs[: dirs.index("--append-system-prompt-file")]
        self.assertIn(str(root), dirs)
        # And nothing else under ~/.claude (an installed root lives there): the agent reads its
        # own saved tool output with the Read tool, which the guard allows without it.
        claude = self.home / ".claude"
        for d in (d for d in dirs if d != str(root)):
            with self.subTest(added=d):
                self.assertFalse(Path(d) == claude or claude in Path(d).parents, d)
        # The reviewed repo's own settings and CLAUDE.md are never loaded.
        self.assertEqual(argv[argv.index("--setting-sources") + 1], "user")
        prompt = Path(argv[argv.index("--append-system-prompt-file") + 1]).read_text()
        self.assertIn(
            "api.github.com", prompt
        )  # the host list, filled in from the settings
        self.assertNotIn("{{HOSTS}}", prompt)
        self.assertIn(
            "--strict-mcp-config", argv
        )  # only the researcher keeps MCP servers
        self.assertNotIn("--resume", argv)
        # After `--`, so a brief that starts with a dash is never read as an option.
        self.assertEqual(argv[-2:], ["--", "Review this."])
        self.assertEqual(Path(call["cwd"]).resolve(), self.work.resolve())
        self.assertTrue((run / "reply.md").read_text().startswith("reply 1\n"))
        self.assertEqual((run / "session_id").read_text(), "sess-1")
        (entry,) = (self.tmp / "sessions.log").read_text().splitlines()
        self.assertEqual(entry.split()[1:], ["cold-reviewer", "sess-1"])

    def test_researcher_keeps_its_mcp_servers(self):
        run = self.run_dir("researcher")
        run.mkdir(parents=True)
        (run / "brief.md").write_text("Research this.\n")
        self.env["STUB_TAIL"] = "RESULT: PASS"
        self.assertEqual(self.run_agent("researcher", self.work, run)[0], 0)
        argv = self.calls_made()[0]["argv"]
        self.assertNotIn("--strict-mcp-config", argv)
        self.assertEqual(argv[argv.index("--max-budget-usd") + 1], "10")

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
        self.assertEqual(second[-2:], ["--", "Send rows 3 to 5."])
        self.assertTrue((run / "reply-1.md").read_text().startswith("reply 1\n"))
        self.assertTrue((run / "reply.md").read_text().startswith("reply 2\n"))

    def test_budget_cap(self):
        run = self.run_dir()
        run.mkdir(parents=True)
        (run / "brief.md").write_text("Review this.\n")
        self.assertEqual(self.run_agent("cold-reviewer", self.work, run)[0], 0)
        self.env["RUN_AGENT_MAX_USD"] = "2"
        self.assertEqual(self.run_agent("cold-reviewer", self.work, run)[0], 0)
        first, second = (c["argv"] for c in self.calls_made())
        self.assertEqual(first[first.index("--max-budget-usd") + 1], "5")
        self.assertEqual(second[second.index("--max-budget-usd") + 1], "2")

    def test_model(self):
        run = self.run_dir()
        run.mkdir(parents=True)
        (run / "brief.md").write_text("Review this.\n")
        self.assertEqual(self.run_agent("cold-reviewer", self.work, run)[0], 0)
        self.env["RUN_AGENT_MODEL"] = "opus"
        self.assertEqual(self.run_agent("cold-reviewer", self.work, run)[0], 0)
        first, second = (c["argv"] for c in self.calls_made())
        self.assertNotIn("--model", first)
        self.assertEqual(second[second.index("--model") + 1], "opus")
        self.assertEqual(second[-1], "Review this.")

    def test_reply_without_its_shape_exits_3(self):
        # A timed-out API call comes back as a "successful" run whose reply is the error text.
        run = self.run_dir()
        run.mkdir(parents=True)
        (run / "brief.md").write_text("Review this.\n")
        for tail in ("Request timed out", "| # | Kind |\nCounts: 3 findings"):
            with self.subTest(tail=tail):
                self.env["STUB_TAIL"] = tail
                code, out = self.run_agent("cold-reviewer", self.work, run)
                self.assertEqual(code, 3, out)
                self.assertIn("isn't in the shape", out)
                self.assertIn(tail.splitlines()[0], (run / "reply.md").read_text())

    def last_line(self, out):
        return out.strip().splitlines()[-1]

    def test_the_last_line_names_the_cost(self):
        run = self.run_dir()
        run.mkdir(parents=True)
        (run / "brief.md").write_text("Review this.\n")
        self.env["STUB_COST"] = "0.42"
        code, out = self.run_agent("cold-reviewer", self.work, run)
        self.assertEqual(code, 0, out)
        self.assertIn("finished (exit 0)", self.last_line(out))
        self.assertTrue(self.last_line(out).endswith("cost $0.42"), out)
        # A run that exits 0 with no readable result ends on its exit 3 line.
        del self.env["STUB_COST"]
        self.env["STUB_RAW"] = "not JSON"
        code, out = self.run_agent("cold-reviewer", self.work, run)
        self.assertEqual(code, 3, out)
        self.assertIn("isn't in the shape", self.last_line(out))
        self.assertTrue(self.last_line(out).endswith("cost unknown"), out)
        # A run that fails ends on its finished line.
        self.env["STUB_EXIT"] = "1"
        code, out = self.run_agent("cold-reviewer", self.work, run)
        self.assertEqual(code, 1, out)
        self.assertIn("finished (exit 1)", self.last_line(out))
        self.assertTrue(self.last_line(out).endswith("cost unknown"), out)

    def test_resume_needs_a_session(self):
        run = self.run_dir()
        run.mkdir(parents=True)
        (run / "followup.md").write_text("More.\n")
        code, out = self.run_agent("cold-reviewer", self.work, run, "--resume")
        self.assertEqual(code, 2)
        self.assertIn("session_id", out)


class RunAgentFromACache(RunAgent):
    """The same tests against a copy of hooks/ in a plugin cache path, with no link under
    ~/.claude: the script finds its agents, guard and settings from where it lives."""

    def setUp(self):
        super().setUp()
        cache = self.home / ".claude/plugins/cache/claude-skills/claude-skills/0.1.0"
        shutil.copytree(REPO / "hooks", cache / "hooks")
        self.script = cache / "hooks" / "run-agent.sh"
        self.assertFalse((self.home / ".claude" / "hooks").exists())
        self.assertFalse((self.home / ".claude" / "skills").exists())


if __name__ == "__main__":
    unittest.main()
