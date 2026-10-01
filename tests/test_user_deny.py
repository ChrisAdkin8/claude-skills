"""Tests for what the README asks someone who installed the plugin to paste.

hooks/user-deny.json holds the deny rules the README asks users to add to their own settings: the
agents' permissions.deny in hooks/agent-sandbox.json, less the rule that hides ~/.cache/agent-runs.
/research, /spec and /cold-review read each agent's reply there (hooks/run-agent.md, step 3), and a
deny rule in the user's settings beats a skill's allowed-tools, so with that rule none of the three
could read a verdict. The expected list is worked out from agent-sandbox.json here, so a rule added
there fails these tests until it is added to user-deny.json too.

Run with: python3 -m unittest discover -s ~/code/github.com/claude-skills/tests
"""

import fnmatch
import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
AGENT = json.loads((REPO / "hooks" / "agent-sandbox.json").read_text())
USER_DENY = REPO / "hooks" / "user-deny.json"
AGENT_RUNS = "Read(~/.cache/agent-runs/**)"
# A reply as the skills read it, in a run dir laid out as hooks/run-agent.md says.
REPLY = "~/.cache/agent-runs/<name>/<agent>/reply.md"


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


if __name__ == "__main__":
    unittest.main()
