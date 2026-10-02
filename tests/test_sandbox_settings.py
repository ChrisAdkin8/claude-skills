"""Tests that the lists of paths agents may not read stay in step: the guard's SECRET_HOME,
HISTORY_HOME and PRIVATE_HOME, which adds all of ~/.claude (hooks/agent-guard.py), the agents' sandbox settings (hooks/agent-sandbox.json), the
spikes' (skills/spec/spike-settings.json) and the implement-verifier's
(skills/implement/verify-settings.json), which denies what the spikes' does. Each file only knows
its own copy, so a path added to one is easily missed in the others. Likewise the secret
environment variables the three sandboxes hide. Also that the skill evals' settings for cases
that launch agents differ from the agents' only as planned.

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
VERIFY = json.loads(
    (REPO / "skills" / "implement" / "verify-settings.json").read_text()
)
AGENT_CASE = json.loads(
    (REPO / "tests" / "skill-evals" / "agent-case-settings.json").read_text()
)
IMPLEMENT_CASE = json.loads(
    (REPO / "tests" / "skill-evals" / "implement-case-settings.json").read_text()
)

# Written-down exceptions, and why.
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
        for path in sorted(self.history):
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
        known = {home_relative(p) for p in guard.PRIVATE_HOME}
        for path in sorted(self.agent_os | self.agent_read):
            with self.subTest(path=path):
                self.assertTrue(
                    covered(path, known), f"~/{path} isn't in the guard's lists"
                )

    def test_spikes_hide_the_secret_env_vars_agents_do(self):
        # A spike runs with no guard and may be given network hosts, and it inherits the
        # environment of the session that launched it: CLAUDE_CODE_MESSAGING_TOKEN is set in
        # every Claude Code session. So its commands may not see the variables the agents' can't.
        self.assertEqual(
            SPIKE["sandbox"].get("credentials", {}).get("envVars"),
            AGENT["sandbox"]["credentials"]["envVars"],
        )

    def test_verify_settings_deny_what_the_spike_settings_deny(self):
        # The verifier runs code in an export as a spike does, under the same sandbox: no
        # network, the same denies and hidden environment variables, and writes only to the uv
        # cache the spikes share.
        for key in ("denyRead", "allowWrite"):
            with self.subTest(list=key):
                self.assertEqual(
                    VERIFY["sandbox"]["filesystem"][key],
                    SPIKE["sandbox"]["filesystem"][key],
                )
        self.assertEqual(VERIFY["permissions"]["deny"], SPIKE["permissions"]["deny"])
        self.assertEqual(
            VERIFY["sandbox"].get("credentials"), SPIKE["sandbox"].get("credentials")
        )
        self.assertEqual(VERIFY["sandbox"]["network"]["allowedDomains"], [])

    def test_os_and_read_denies_match(self):
        # The agents' sandbox also denies all of ~/.claude to Bash. The Read tool can't take that
        # deny: it would beat any allow and hide the agent's own saved tool output, so the guard
        # is the Read tool's allow-list there.
        for name, os_deny, read_deny in (
            ("agent-sandbox.json", self.agent_os, self.agent_read | {".claude"}),
            ("spike-settings.json", self.spike_os, self.spike_read),
            (
                "verify-settings.json",
                entries(VERIFY["sandbox"]["filesystem"]["denyRead"]),
                entries(VERIFY["permissions"]["deny"]),
            ),
        ):
            with self.subTest(file=name):
                self.assertEqual(os_deny, read_deny)

    def test_agent_sandbox_reopens_only_the_plugin_root(self):
        # The plugin's files sit under ~/.claude when installed, so the ~/.claude deny needs this
        # one exception for Bash to run the skill scripts.
        for name, settings in (
            ("agent-sandbox.json", AGENT),
            ("agent-case-settings.json", AGENT_CASE),
        ):
            with self.subTest(file=name):
                self.assertIn("~/.claude", settings["sandbox"]["filesystem"]["denyRead"])
                self.assertEqual(
                    settings["sandbox"]["filesystem"].get("allowRead"),
                    ["${CLAUDE_PLUGIN_ROOT}"],
                )

    def test_agent_case_settings_differ_only_as_planned(self):
        # The skill evals that launch agents use tests/skill-evals/agent-case-settings.json. It is
        # agent-sandbox.json with run-agent.sh outside this sandbox (the agent's session has its
        # own), and ~/.cache/agent-runs readable, so the skill can read reply.md. And the Write and
        # Edit tools, which the OS sandbox doesn't cover, may not touch the real ~/notes/index.md:
        # a Sonnet run rewrote it by hand when build-index.py was refused. Nothing else.
        expected = json.loads(json.dumps(AGENT))
        sandbox = expected["sandbox"]
        sandbox["excludedCommands"].append("${CLAUDE_PLUGIN_ROOT}/hooks/run-agent.sh *")
        sandbox["filesystem"]["denyRead"].remove("~/.cache/agent-runs")
        deny = expected["permissions"]["deny"]
        deny.remove("Read(~/.cache/agent-runs/**)")
        deny += ["Write(~/notes/index.md)", "Edit(~/notes/index.md)"]
        self.assertEqual(AGENT_CASE, expected)

    def test_implement_case_settings_differ_only_in_the_sandbox(self):
        # The implement eval cases run /implement, whose worktree, commits and
        # ~/.cache/implement-runs writes the sandbox refuses (spike S1 of
        # docs/specs/2026-09-26-implement-skill-2-skill.md). So they keep the agents' permission
        # denies, which the Read tool obeys, and turn the OS sandbox off. Nothing else.
        expected = json.loads(json.dumps(AGENT))
        expected["sandbox"] = {"enabled": False}
        self.assertEqual(IMPLEMENT_CASE, expected)

    def test_no_settings_file_locates_the_repo_through_home(self):
        # The `~/.claude` entries in the spike settings are denies (all of ~/.claude, plugins
        # included), so they stay. The others may name the repo only with the placeholder.
        for name, settings in (
            ("spike-settings.json", SPIKE),
            ("verify-settings.json", VERIFY),
        ):
            allowed = list(settings["sandbox"].get("excludedCommands", []))
            allowed += settings.get("permissions", {}).get("allow", [])
            allowed += settings["sandbox"]["filesystem"].get("allowWrite", [])
            for entry in allowed:
                with self.subTest(file=name, entry=entry):
                    self.assertNotIn("~/.claude", entry)
        for name, settings in (
            ("agent-sandbox.json", AGENT),
            ("agent-case-settings.json", AGENT_CASE),
        ):
            allowed = list(settings["sandbox"]["excludedCommands"])
            allowed += settings["sandbox"]["filesystem"].get("allowRead", [])
            with self.subTest(file=name):
                self.assertEqual([e for e in allowed if "~/.claude" in e], [])


if __name__ == "__main__":
    unittest.main()
