"""Tests for what the README asks someone who installed the plugin to paste.

hooks/user-deny.json holds the deny rules the README asks users to add to their own settings: the
agents' permissions.deny in hooks/agent-sandbox.json, less the rule that hides ~/.cache/agent-runs.
/research, /spec and /cold-review read each agent's reply there (hooks/run-agent.md, step 3), and a
deny rule in the user's settings beats a skill's allowed-tools, so with that rule none of the three
could read a verdict. The expected list is worked out from agent-sandbox.json here, so a rule added
there fails these tests until it is added to user-deny.json too.

The README's command that rebuilds the notes index from the installed plugin is run as the README
writes it, in a scratch HOME. Claude Code installs each version of a plugin in a folder of its own
under ~/.claude/plugins/cache, and after an update it keeps the old one for 14 days, marked with an
.orphaned_at file. So a glob over the version folders can match two copies, which build-index.py
refuses; and writing that marker makes the old folder the newest, so the newest isn't the right
one either. The command must find the installed copy's folder in installed_plugins.json.

Run with: python3 -m unittest discover -s ~/code/github.com/claude-skills/tests
"""

import fnmatch
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
AGENT = json.loads((REPO / "hooks" / "agent-sandbox.json").read_text())
USER_DENY = REPO / "hooks" / "user-deny.json"
AGENT_RUNS = "Read(~/.cache/agent-runs/**)"
# A reply as the skills read it, in a run dir laid out as hooks/run-agent.md says.
REPLY = "~/.cache/agent-runs/<name>/<agent>/reply.md"
FENCE = re.compile(r"^```[^\n]*\n(.*?)^```", re.MULTILINE | re.DOTALL)


def readme_index_commands():
    """Each fenced block or inline code span in the README that runs build-index.py from the
    installed plugin, which is the code that names both build-index.py and ~/.claude/plugins."""
    text = (REPO / "README.md").read_text()
    code = FENCE.findall(text) + re.findall(r"`([^`\n]+)`", FENCE.sub("", text))
    return [c for c in code if "build-index.py" in c and "~/.claude/plugins" in c]


class UserDeny(unittest.TestCase):
    def setUp(self):
        self.assertTrue(USER_DENY.is_file(), f"{USER_DENY} is missing")
        self.user = json.loads(USER_DENY.read_text())

    def test_shape_to_merge_into_settings(self):
        # Only what a user merges into ~/.claude/settings.json: no other keys to copy by mistake.
        self.assertEqual(list(self.user), ["permissions"])
        self.assertEqual(list(self.user["permissions"]), ["deny"])
        deny = self.user["permissions"]["deny"]
        self.assertIsInstance(deny, list)
        for rule in deny:
            with self.subTest(rule=rule):
                self.assertIsInstance(rule, str)
                self.assertTrue(rule)
        self.assertEqual(len(deny), len(set(deny)), "a rule is listed twice")

    def test_the_agents_denies_less_agent_runs(self):
        # As tests/test_sandbox_settings.py checks agent-case-settings.json: start from the agents'
        # list, make the one planned change, and compare the whole file.
        deny = json.loads(json.dumps(AGENT["permissions"]["deny"]))
        deny.remove(AGENT_RUNS)
        self.assertEqual(self.user, {"permissions": {"deny": deny}})

    def test_replies_stay_readable(self):
        # Not the agent-runs rule, nor any wider rule that would hide a reply all the same.
        deny = self.user["permissions"]["deny"]
        self.assertNotIn(AGENT_RUNS, deny)
        for rule in deny:
            with self.subTest(rule=rule):
                path = rule.removeprefix("Read(").removesuffix(")")
                self.assertFalse(
                    fnmatch.fnmatchcase(REPLY, path),
                    f"{rule} hides the agents' replies",
                )


class ReadmeIndexCommand(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.home)
        (self.home / "notes" / "research").mkdir(parents=True)
        versions = self.home / ".claude/plugins/cache/claude-skills/claude-skills"
        # The installed version, with the real scripts.
        self.installed = versions / "4e1b2c3d4f5a"
        shutil.copytree(
            REPO / "skills" / "research" / "scripts",
            self.installed / "skills" / "research" / "scripts",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        os.utime(self.installed, (1_700_000_000, 1_700_000_000))
        # The version an update replaced: kept, marked, and so the newest folder.
        old = versions / "0.1.0"
        stub = old / "skills" / "research" / "scripts" / "build-index.py"
        stub.parent.mkdir(parents=True)
        stub.write_text('import sys\nsys.exit("ran the orphaned copy")\n')
        (old / ".orphaned_at").write_text("1790812800000\n")
        self.assertGreater(old.stat().st_mtime, self.installed.stat().st_mtime)
        install = {
            "scope": "user",
            "installPath": str(self.installed),
            "version": self.installed.name,
            "installedAt": "2026-10-01T09:00:00.000Z",
            "lastUpdated": "2026-10-01T09:00:00.000Z",
            "gitCommitSha": self.installed.name + "0" * 28,
        }
        record = {"version": 2, "plugins": {"claude-skills@claude-skills": [install]}}
        (self.home / ".claude/plugins/installed_plugins.json").write_text(
            json.dumps(record, indent=2)
        )

    def test_runs_the_installed_copy(self):
        found = readme_index_commands()
        self.assertEqual(len(found), 1, f"want one command, found {found}")
        # bash, and zsh, macOS's own shell, where there is one; neither reads the user's startup
        # files, so only the command decides what runs.
        shells = {"bash": ["bash", "-c"], "zsh": ["zsh", "-f", "-c"]}
        self.assertTrue(shutil.which("bash"))
        index = self.home / "notes" / "index.md"
        for name, argv in shells.items():
            if not shutil.which(name):
                continue
            with self.subTest(shell=name):
                index.unlink(missing_ok=True)
                out = subprocess.run(
                    argv + [found[0]],
                    cwd=self.home,
                    env={"HOME": str(self.home), "PATH": os.environ["PATH"]},
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                self.assertEqual(out.returncode, 0, out.stderr)
                self.assertTrue(index.is_file(), out.stdout + out.stderr)
                self.assertIn("0 topics, 0 notes, 0 unfiled", out.stdout)


if __name__ == "__main__":
    unittest.main()
