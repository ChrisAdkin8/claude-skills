"""Tests for hooks/run-name.py: the safe name the skills build run dirs, worktrees, branches and
scratch folders from, for a repo folder or document whose name has spaces, accents or other
characters the launchers refuse.

Run with: python3 -m unittest discover -s tests
"""

import fnmatch
import re
import subprocess
import sys
import unicodedata
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "hooks" / "run-name.py"
# The launchers' own pattern (hooks/run-agent.sh, run-implementer.sh, run-verify.sh,
# prepare-verify.sh, run-spike.sh, prepare-spike.sh; ledger.py too).
LAUNCHERS = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def run_name(name):
    run = subprocess.run(
        [str(SCRIPT), name], capture_output=True, text=True, check=True
    )
    lines = run.stdout.splitlines()
    assert len(lines) == 1, run.stdout
    return lines[0]


class RunName(unittest.TestCase):
    def test_is_executable(self):
        self.assertTrue(SCRIPT.stat().st_mode & 0o111)

    def test_a_name_that_fits_is_unchanged(self):
        for name in (
            "my-app",
            "claude-skills",
            "2026-10-07-usability-2a-refuses-early",
            "a.b_c",
        ):
            with self.subTest(name=name):
                self.assertEqual(run_name(name), name)

    def test_unusual_names_map_to_names_the_launchers_accept(self):
        for name in (
            "Design Notes",
            "My App",
            "_infra",
            "café",
            "api+web",
            "日本",
            "___",
            "",
            "-x",
            ".hidden",
        ):
            with self.subTest(name=name):
                got = run_name(name)
                self.assertRegex(got, r"\A" + LAUNCHERS.pattern + r"\Z")
                self.assertEqual(run_name(name), got, "not the same each time")

    def test_the_mapped_name_reads_like_the_original(self):
        self.assertRegex(run_name("Design Notes"), r"\ADesign-Notes-[0-9a-f]{6}\Z")
        self.assertRegex(run_name("café"), r"\Acafe-[0-9a-f]{6}\Z")
        self.assertRegex(run_name("_infra"), r"\Ainfra-[0-9a-f]{6}\Z")
        # Nothing ASCII left: `x` before the hash, as a name must start with a letter or digit.
        self.assertRegex(run_name("日本"), r"\Ax-[0-9a-f]{6}\Z")
        self.assertRegex(run_name("___"), r"\Ax-[0-9a-f]{6}\Z")

    def test_different_names_get_different_names(self):
        self.assertNotEqual(run_name("Design Notes"), run_name("Design-Notes"))
        self.assertNotEqual(run_name("Design Notes"), run_name("Design_Notes!"))
        self.assertNotEqual(run_name("日本"), run_name("中国"))

    def test_both_forms_of_an_accent_give_one_name(self):
        composed = unicodedata.normalize("NFC", "café")
        decomposed = unicodedata.normalize("NFD", "café")
        self.assertNotEqual(composed, decomposed)
        self.assertEqual(run_name(composed), run_name(decomposed))

    def test_the_branch_it_builds_is_valid(self):
        for name in ("Design Notes", "café", "日本", "My App"):
            with self.subTest(name=name):
                check = subprocess.run(
                    ["git", "check-ref-format", "--branch", f"implement/{run_name(name)}"],
                    capture_output=True, text=True, check=False,
                )  # fmt: skip
                self.assertEqual(check.returncode, 0, check.stderr)

    def test_each_skill_that_builds_names_pre_approves_it(self):
        sys.path.insert(0, str(REPO / "tests"))
        from test_skill_frontmatter import allowed_tools

        command = "${CLAUDE_PLUGIN_ROOT}/hooks/run-name.py <name>"
        for skill in ("implement", "spec", "cold-review", "research"):
            with self.subTest(skill=skill):
                path = REPO / "skills" / skill / "SKILL.md"
                rules = re.findall(r"Bash\(([^)]*)\)", allowed_tools(path))
                self.assertTrue(
                    any(fnmatch.fnmatchcase(command, rule) for rule in rules), rules
                )
                self.assertIn("run-name.py", path.read_text().split("---", 2)[2])

    def test_usage(self):
        for args in ((), ("a", "b")):
            with self.subTest(args=args):
                run = subprocess.run(
                    [str(SCRIPT), *args], capture_output=True, text=True, check=False
                )
                self.assertEqual(run.returncode, 2)
                self.assertIn("usage", run.stderr)


if __name__ == "__main__":
    unittest.main()
