"""Tests for the skills' allowed-tools: every path rule there is one Claude Code consults.

Claude Code checks file permissions against `Edit(path)` and `Read(path)` rules only. A path rule
for `Write`, `NotebookEdit`, `Glob` or `MultiEdit` is accepted and never consulted
(code.claude.com/docs/en/permissions, "Read and Edit"), so a skill that pre-approves its writes
with `Write(~/x/**)` still asks, or is refused when no one can answer. `Edit(path)` covers the
Write tool too. Eval round 1 on 2026-10-01 found /implement's verifier writes refused this way.

Run with: python3 -m unittest discover -s tests
"""

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILLS = sorted((REPO / "skills").glob("*/SKILL.md"))
# A rule for one of these tools with a path in brackets: accepted, then ignored.
IGNORED_PATH_RULE = re.compile(r"\b(Write|NotebookEdit|Glob|MultiEdit)\(([^)]*)\)")


def allowed_tools(skill):
    """The frontmatter's allowed-tools value, with its continuation lines joined."""
    lines = skill.read_text().splitlines()
    end = lines.index("---", 1)
    value, inside = [], False
    for line in lines[1:end]:
        if line.startswith("allowed-tools:"):
            value.append(line.split(":", 1)[1])
            inside = True
        elif inside and line.startswith((" ", "\t")):
            value.append(line)
        else:
            inside = False
    return " ".join(value)


class AllowedTools(unittest.TestCase):
    def test_every_skill_is_checked(self):
        self.assertGreaterEqual(len(SKILLS), 5)
        for skill in SKILLS:
            with self.subTest(skill=skill.parent.name):
                self.assertTrue(allowed_tools(skill).strip(), "no allowed-tools")

    def test_no_path_rule_claude_code_ignores(self):
        for skill in SKILLS:
            with self.subTest(skill=skill.parent.name):
                found = IGNORED_PATH_RULE.findall(allowed_tools(skill))
                self.assertEqual(
                    found,
                    [],
                    "use Edit(path) for writes: these rules are never consulted",
                )

    def test_the_pattern_catches_what_it_should(self):
        self.assertTrue(IGNORED_PATH_RULE.search("Read Write(~/.cache/x/**) Skill"))
        self.assertTrue(IGNORED_PATH_RULE.search("Glob(~/notes/**)"))
        self.assertFalse(
            IGNORED_PATH_RULE.search("Read Write Edit(~/.cache/x/**) Skill")
        )
        self.assertFalse(IGNORED_PATH_RULE.search("Bash(git commit *)"))


if __name__ == "__main__":
    unittest.main()
