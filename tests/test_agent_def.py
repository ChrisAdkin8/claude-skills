"""Tests for hooks/agent-def.py: each agent file converts to the JSON `claude --agents` takes,
keeping its tools and guard hooks, and a file it can't fully read is refused.

Run with: python3 -m unittest discover -s ~/code/github.com/claude-skills/tests
"""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "hooks" / "agent-def.py"
AGENTS = REPO / "hooks" / "agents"
NAMES = ("researcher", "research-verifier", "spec-verifier", "cold-reviewer")
ROOT = "/opt/plugin root"
GUARD = f'python3 "{ROOT}/hooks/agent-guard.py"'
MINIMAL = """---
name: probe
description: A probe.
tools: Read, Bash
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: python3 guard.py bash
---

Do the thing.
"""


def convert(path, *extra, root=ROOT):
    args = ["--root", root] if root else []
    run = subprocess.run(
        [str(SCRIPT), *args, str(path), *extra],
        capture_output=True,
        text=True,
        check=False,
    )
    return run.returncode, run.stdout, run.stderr


class AgentDef(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def probe(self, text, name="probe", **kw):
        path = self.tmp / f"{name}.md"
        path.write_text(text)
        return convert(path, **kw)

    def test_each_agent_converts(self):
        for name in NAMES:
            with self.subTest(agent=name):
                code, out, err = convert(AGENTS / f"{name}.md")
                self.assertEqual(code, 0, err)
                ((key, agent),) = json.loads(out).items()
                self.assertEqual(key, name)
                self.assertEqual(
                    set(agent), {"description", "prompt", "tools", "hooks"}
                )
                self.assertIn("not for general use", agent["description"])
                self.assertNotIn("---", agent["prompt"].splitlines()[0])
                # Every agent's Bash and file reads go through the guard.
                commands = {
                    m["matcher"]: [h["command"] for h in m["hooks"]]
                    for m in agent["hooks"]["PreToolUse"]
                }
                self.assertEqual(commands["Bash"], [f"{GUARD} bash"])
                self.assertEqual(commands["Read|Grep|Glob"], [f"{GUARD} read"])

    def test_researcher_keeps_its_write_hook_and_mcp_tools(self):
        code, out, err = convert(AGENTS / "researcher.md")
        self.assertEqual(code, 0, err)
        agent = json.loads(out)["researcher"]
        (write,) = [
            m for m in agent["hooks"]["PreToolUse"] if m["matcher"] == "Write|Edit"
        ]
        self.assertEqual(
            write["hooks"],
            [{"type": "command", "command": f'{GUARD} write "$HOME/notes/research"'}],
        )
        mcp = [t for t in agent["tools"] if t.startswith("mcp__")]
        self.assertIn("mcp__plugin_aws-core_aws-mcp__aws___search_documentation", mcp)
        self.assertIn("mcp__plugin_terraform_terraform__get_policy_details", mcp)
        self.assertEqual(len(mcp), 13)
        self.assertEqual(
            agent["tools"][:6],
            ["Read", "Write", "Edit", "Bash", "WebSearch", "WebFetch"],
        )

    def test_minimal_file(self):
        code, out, err = self.probe(MINIMAL)
        self.assertEqual(code, 0, err)
        self.assertEqual(
            json.loads(out),
            {
                "probe": {
                    "description": "A probe.",
                    "prompt": "Do the thing.\n",
                    "tools": ["Read", "Bash"],
                    "hooks": {
                        "PreToolUse": [
                            {
                                "matcher": "Bash",
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "python3 guard.py bash",
                                    }
                                ],
                            }
                        ]
                    },
                }
            },
        )

    def test_refuses_what_it_cant_fully_read(self):
        cases = {
            "unknown key": MINIMAL.replace("tools:", "model: haiku\ntools:"),
            "other hook type": MINIMAL.replace("type: command", "type: prompt"),
            "extra hook field": MINIMAL.replace(
                "command: python3 guard.py bash",
                "command: python3 guard.py bash\n          timeout: 5",
            ),
            "hook with no command": MINIMAL.replace(
                "          command: python3 guard.py bash\n", ""
            ),
            "no tools": MINIMAL.replace("tools: Read, Bash\n", ""),
            "no frontmatter": "Do the thing.\n",
            "no prompt": MINIMAL.replace("Do the thing.\n", ""),
        }
        for label, text in cases.items():
            with self.subTest(case=label):
                code, out, err = self.probe(text)
                self.assertEqual(code, 2, out)
                self.assertEqual(out, "")
                self.assertIn("agent-def:", err)

    def test_root_replaces_the_placeholder_in_commands_and_prompt(self):
        text = MINIMAL.replace(
            "python3 guard.py bash", 'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/guard.py" bash'
        ).replace("Do the thing.", "Run ${CLAUDE_PLUGIN_ROOT}/skills/x.sh twice.")
        code, out, err = self.probe(text, root="/r/p")
        self.assertEqual(code, 0, err)
        agent = json.loads(out)["probe"]
        self.assertEqual(agent["prompt"], "Run /r/p/skills/x.sh twice.\n")
        (hook,) = agent["hooks"]["PreToolUse"][0]["hooks"]
        self.assertEqual(hook["command"], 'python3 "/r/p/hooks/guard.py" bash')

    def test_no_placeholder_survives(self):
        for name in NAMES:
            with self.subTest(agent=name):
                code, out, err = convert(AGENTS / f"{name}.md")
                self.assertEqual(code, 0, err)
                self.assertNotIn("${CLAUDE_PLUGIN_ROOT}", out)
                self.assertNotIn("~/.claude/skills", out)
                self.assertNotIn("~/.claude/hooks", out)
                self.assertIn(ROOT, out)

    def test_agent_prompts_name_their_scripts_by_the_root(self):
        for name in ("researcher", "research-verifier"):
            with self.subTest(agent=name):
                out = json.loads(convert(AGENTS / f"{name}.md")[1])[name]["prompt"]
                self.assertIn(f"{ROOT}/skills/research/scripts/repo-health.sh", out)

    def test_placeholder_without_a_root_is_refused(self):
        text = MINIMAL.replace("guard.py", "${CLAUDE_PLUGIN_ROOT}/guard.py")
        code, out, err = self.probe(text, root=None)
        self.assertEqual(code, 2, out)
        self.assertEqual(out, "")
        self.assertIn("--root", err)
        self.assertEqual(convert(AGENTS / "researcher.md", root=None)[0], 2)

    def test_another_variable_in_a_command_is_refused(self):
        for var in ("${HOME}", "${CLAUDE_PLUGIN_DATA}", "${x}"):
            with self.subTest(var=var):
                text = MINIMAL.replace("guard.py", f"{var}/guard.py")
                code, out, err = self.probe(text)
                self.assertEqual(code, 2, out)
                self.assertEqual(out, "")
                self.assertIn("agent-def:", err)
                self.assertIn("${", err)

    def test_bad_arguments(self):
        path = self.tmp / "probe.md"
        path.write_text(MINIMAL)
        for args in (
            [],
            [str(path), str(path)],
            ["--root", str(path)],
            ["--root", "/r", "--root", "/s", str(path)],
            ["--nope", str(path)],
            ["--root", "", str(path)],
        ):
            with self.subTest(args=args):
                run = subprocess.run(
                    [str(SCRIPT), *args], capture_output=True, text=True, check=False
                )
                self.assertEqual(run.returncode, 2, run.stdout)

    def test_name_must_match_the_file(self):
        code, _, err = self.probe(MINIMAL, name="other")
        self.assertEqual(code, 2)
        self.assertIn("doesn't match", err)


if __name__ == "__main__":
    unittest.main()
