"""Tests for tests/mine-sessions.py: it splits sessions into skill runs, counts agent launches and
follow-ups, spots a launch joined to another command, groups failed tool calls (guard refusals by
their reason), lists what the user typed, reports headless agent sessions from sessions.log, and
honours --since. It reads only the made-up logs in a temporary directory.
Run with: python3 -m unittest discover -s ~/code/github.com/claude-skills/tests
"""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "mine-sessions.py"
GUARD = (
    'PreToolUse:Bash hook error: [python3 "$HOME/.claude/hooks/agent-guard.py" bash]: Blocked by'
    " agent-guard: `awk` isn't on this agent's command list: reading and text tools"
)


def user(text, when="2026-09-20T10:00:00Z"):
    return {
        "type": "user",
        "timestamp": when,
        "message": {"role": "user", "content": text},
    }


def command(name, args, when="2026-09-20T10:00:00Z"):
    return user(
        f"<command-message>{name}</command-message>\n<command-name>/{name}</command-name>\n"
        f"<command-args>{args}</command-args>",
        when,
    )


def tool_use(uid, name, tool_input, msg_id, tokens=(10, 5)):
    return {
        "type": "assistant",
        "timestamp": "2026-09-20T10:01:00Z",
        "message": {
            "id": msg_id,
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": uid, "name": name, "input": tool_input}
            ],
            "usage": {
                "input_tokens": tokens[0],
                "output_tokens": tokens[1],
                "cache_read_input_tokens": 100,
            },
        },
    }


def result(uid, text, error=False):
    return {
        "type": "user",
        "timestamp": "2026-09-20T10:02:00Z",
        "message": {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": uid,
                    "content": text,
                    "is_error": error,
                }
            ],
        },
    }


class MineSessions(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.projects = self.tmp / "projects"
        self.log = self.tmp / "sessions.log"
        self.log.write_text("")

    def session(self, project, sid, events):
        folder = self.projects / project
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{sid}.jsonl").write_text(
            "\n".join(json.dumps(e) for e in events) + "\nnot json\n"
        )

    def run_miner(self, *args):
        run = subprocess.run(
            [
                str(SCRIPT),
                "--projects",
                str(self.projects),
                "--sessions-log",
                str(self.log),
                *args,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        return run.returncode, run.stdout + run.stderr

    def test_a_spec_run(self):
        self.session(
            "-repo",
            "aaaaaaaa-1",
            [
                command("spec", "quick add a flag"),
                tool_use(
                    "t1",
                    "Bash",
                    {
                        "command": "~/.claude/hooks/run-agent.sh spec-verifier ~/r ~/.cache/agent-runs/r--s/spec-verifier"
                    },
                    "m1",
                ),
                result("t1", "run-agent: spec-verifier finished (exit 0)"),
                tool_use(
                    "t2",
                    "Bash",
                    {
                        "command": '~/.claude/hooks/run-agent.sh spec-verifier ~/r ~/.cache/agent-runs/r--s/spec-verifier --resume; echo "exit=$?"'
                    },
                    "m2",
                ),
                result(
                    "t2", "Exit code 2\nrun-agent: write followup.md first", error=True
                ),
                tool_use(
                    "t3", "Bash", {"command": "grep -n x hooks/run-agent.sh"}, "m3"
                ),
                result("t3", "Exit code 1", error=True),
                user("no, don't do that"),
                user("<task-notification>done</task-notification>"),
                command("cold-review", "docs/specs/x.md"),
                tool_use("t4", "Bash", {"command": "ls"}, "m4"),
                result("t4", "Exit code 1", error=True),
            ],
        )
        code, out = self.run_miner()
        self.assertEqual(code, 0, out)
        spec = out.split("## /spec:")[1].split("## /")[0]
        self.assertIn("1 runs (quick 1)", spec)
        self.assertIn("Turns 3 · tokens in 30", spec)
        self.assertIn("Agent launches: spec-verifier 2 (1 follow-ups)", spec)
        self.assertIn("Launches joined to another command: 1", spec)
        self.assertIn("Failed tool calls: 2", spec)
        self.assertIn("Bash · exit 2", spec)
        self.assertIn("Bash · exit 1", spec)
        self.assertIn(
            'You typed 1 messages after starting it\n    2026-09-20 aaaaaaaa "no, don\'t do that"',
            spec,
        )
        review = out.split("## /cold-review:")[1].split("## ")[0]
        self.assertIn("1 runs (main 1)", review)
        self.assertIn("Failed tool calls: 1", review)
        self.assertIn("## /research: no runs", out)

    def test_a_skill_started_by_the_skill_tool(self):
        self.session(
            "-repo",
            "bbbbbbbb-1",
            [
                user("look into this"),
                tool_use("s1", "Skill", {"skill": "research", "args": "ideas x"}, "m1"),
            ],
        )
        code, out = self.run_miner()
        self.assertEqual(code, 0, out)
        self.assertIn("## /research: 1 runs (ideas 1)", out)

    def test_agent_sessions_and_guard_refusals(self):
        self.log.write_text("2026-09-20T10:00:00Z cold-reviewer cccccccc-1\n")
        self.session(
            "-repo",
            "cccccccc-1",
            [
                user("Review x adversarially."),
                tool_use("g1", "Bash", {"command": "awk 'NR==1' README.md"}, "m1"),
                result("g1", GUARD, error=True),
            ],
        )
        code, out = self.run_miner()
        self.assertEqual(code, 0, out)
        self.assertIn("Headless agent sessions: 1 found of 1", out)
        agent = out.split("## agent cold-reviewer:")[1]
        self.assertIn("1 sessions", agent)
        self.assertIn("Bash · guard: `awk` isn't on this agent's command list", agent)
        self.assertIn("e.g. 2026-09-20 cccccccc awk 'NR==1' README.md", agent)
        # An agent's session isn't mistaken for a skill run.
        self.assertIn("## /cold-review: no runs", out)

    def test_since(self):
        self.session("-repo", "old", [command("spec", "x", "2026-08-01T10:00:00Z")])
        self.session(
            "-repo", "new", [command("spec", "done x", "2026-09-20T10:00:00Z")]
        )
        code, out = self.run_miner("--since", "2026-09-01")
        self.assertEqual(code, 0, out)
        self.assertIn("Session logs: read 1 of 2 (active since 2026-09-01)", out)
        self.assertIn("## /spec: 1 runs (done 1)", out)

    def test_bad_input(self):
        code, out = self.run_miner("--since", "yesterday")
        self.assertEqual(code, 2, out)
        self.projects = self.tmp / "missing"
        code, out = self.run_miner()
        self.assertEqual(code, 2, out)
        self.assertIn("no session logs", out)


if __name__ == "__main__":
    unittest.main()
