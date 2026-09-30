"""Tests that the three lists of paths agents may not read stay in step: the guard's SECRET_HOME
and HISTORY_HOME (hooks/agent-guard.py), the agents' sandbox settings (hooks/agent-sandbox.json)
and the spikes' (skills/spec/spike-settings.json). Each file only knows its own copy, so a path
added to one is easily missed in the others. Also that the skill evals' settings for cases that
launch agents differ from the agents' only as planned.

Run with: python3 -m unittest discover -s ~/code/github.com/claude-skills/tests
"""

import importlib.util
import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "agent_guard", REPO / "hooks" / "agent-guard.py"
)
assert spec and spec.loader
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

AGENT = json.loads((REPO / "hooks" / "agent-sandbox.json").read_text())
SPIKE = json.loads((REPO / "skills" / "spec" / "spike-settings.json").read_text())
AGENT_CASE = json.loads(
    (REPO / "tests" / "skill-evals" / "agent-case-settings.json").read_text()
)

# Written-down exceptions, and why.
# The agent's own tool output is saved under ~/.claude/projects, so only the guard covers it.
# Likewise ~/.claude/plugins: the guard exempts its own root there, which a deny can't say.
AGENT_NOT_DENIED = {".claude/projects", ".claude/plugins"}
# git and uv read their own config under ~/.config, so a spike is denied only parts of it.
SPIKE_PARTLY_DENIED = {
    ".config": {".config/gh", ".config/gcloud", ".config/op", ".config/doctl"}
}


def home_relative(path):
    """'.ssh' for Path.home() / '.ssh'."""
    return str(Path(path).relative_to(guard.HOME))


def entries(values):
    """'~/.ssh' and 'Read(~/.ssh/**)' both as '.ssh'; other kinds of rule are left out."""
    out = set()
    for v in values:
        if v.startswith("Read(") and v.endswith(")"):
            v = v[len("Read(") : -1]
        elif "(" in v:
            continue
        v = v.removesuffix("/**")
        if v.startswith("~/"):
            out.add(v[2:])
    return out


def covered(path, denied):
    """Whether `path` or a directory above it is denied."""
    parts = Path(path).parts
    return any(Path(*parts[:n]).as_posix() in denied for n in range(1, len(parts) + 1))


class SandboxSettings(unittest.TestCase):
    def setUp(self):
        self.agent_os = entries(AGENT["sandbox"]["filesystem"]["denyRead"])
        self.agent_read = entries(AGENT["permissions"]["deny"])
        self.spike_os = entries(SPIKE["sandbox"]["filesystem"]["denyRead"])
        self.spike_read = entries(SPIKE["permissions"]["deny"])
        self.secrets = {home_relative(p) for p in guard.SECRET_HOME}
        self.history = {home_relative(p) for p in guard.HISTORY_HOME}

    def test_secrets_denied_to_agents_and_spikes(self):
        for path in sorted(self.secrets):
            for name, denied in (
                ("agent-sandbox.json denyRead", self.agent_os),
                ("agent-sandbox.json Read denies", self.agent_read),
                ("spike-settings.json denyRead", self.spike_os),
                ("spike-settings.json Read denies", self.spike_read),
            ):
                with self.subTest(path=path, list=name):
                    if name.startswith("spike") and path in SPIKE_PARTLY_DENIED:
                        self.assertLessEqual(SPIKE_PARTLY_DENIED[path], denied)
                    else:
                        self.assertTrue(
                            covered(path, denied), f"~/{path} missing from {name}"
                        )

    def test_history_denied_to_agents_and_spikes(self):
        for path in sorted(self.history - AGENT_NOT_DENIED):
            for name, denied in (
                ("agent-sandbox.json denyRead", self.agent_os),
                ("agent-sandbox.json Read denies", self.agent_read),
            ):
                with self.subTest(path=path, list=name):
                    self.assertTrue(
                        covered(path, denied), f"~/{path} missing from {name}"
                    )
        for path in sorted(self.history):
            for name, denied in (
                ("spike-settings.json denyRead", self.spike_os),
                ("spike-settings.json Read denies", self.spike_read),
            ):
                with self.subTest(path=path, list=name):
                    self.assertTrue(
                        covered(path, denied), f"~/{path} missing from {name}"
                    )

    def test_agent_denies_known_to_guard(self):
        # A path the sandbox denies but the guard doesn't know is still readable with the Read
        # tool, which the OS sandbox doesn't cover.
        known = self.secrets | self.history
        for path in sorted(self.agent_os | self.agent_read):
            with self.subTest(path=path):
                self.assertTrue(
                    covered(path, known), f"~/{path} isn't in the guard's lists"
                )

    def test_os_and_read_denies_match(self):
        for name, os_deny, read_deny in (
            ("agent-sandbox.json", self.agent_os, self.agent_read),
            ("spike-settings.json", self.spike_os, self.spike_read),
        ):
            with self.subTest(file=name):
                self.assertEqual(os_deny, read_deny)

    def test_agent_case_settings_differ_only_as_planned(self):
        # The skill evals that launch agents use tests/skill-evals/agent-case-settings.json. It is
        # agent-sandbox.json with run-agent.sh outside this sandbox (the agent's session has its
        # own), and ~/.cache/agent-runs readable, so the skill can read reply.md. And the Write and
        # Edit tools, which the OS sandbox doesn't cover, may not touch the real ~/notes/index.md:
        # a Sonnet run rewrote it by hand when build-index.py was refused. Nothing else.
        expected = json.loads(json.dumps(AGENT))
        sandbox = expected["sandbox"]
        # Both spellings of run-agent.sh, since the skills still call the `~` one until part 2's W3.
        sandbox["excludedCommands"] += [
            "${CLAUDE_PLUGIN_ROOT}/hooks/run-agent.sh *",
            "~/.claude/hooks/run-agent.sh *",
        ]
        sandbox["filesystem"]["denyRead"].remove("~/.cache/agent-runs")
        deny = expected["permissions"]["deny"]
        deny.remove("Read(~/.cache/agent-runs/**)")
        deny += ["Write(~/notes/index.md)", "Edit(~/notes/index.md)"]
        self.assertEqual(AGENT_CASE, expected)

    def test_no_settings_file_locates_the_repo_through_home(self):
        # The `~/.claude` entries in the spike settings are denies (all of ~/.claude, plugins
        # included), so they stay. The others may name the repo only with the placeholder or, for
        # the legacy spelling, in the two agent files' excludedCommands until part 2's W3.
        for name, settings in (("spike-settings.json", SPIKE),):
            allowed = list(settings["sandbox"].get("excludedCommands", []))
            allowed += settings.get("permissions", {}).get("allow", [])
            allowed += settings["sandbox"]["filesystem"].get("allowWrite", [])
            for entry in allowed:
                with self.subTest(file=name, entry=entry):
                    self.assertNotIn("~/.claude", entry)
        for name, settings in (("agent-sandbox.json", AGENT), ("agent-case-settings.json", AGENT_CASE)):
            legacy = [e for e in settings["sandbox"]["excludedCommands"] if "~/.claude" in e]
            with self.subTest(file=name):
                self.assertTrue(all(e.startswith(("~/.claude/skills/research/scripts/", "~/.claude/hooks/run-agent.sh")) for e in legacy), legacy)


if __name__ == "__main__":
    unittest.main()
