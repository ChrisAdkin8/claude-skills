"""Tests for hooks/agent-guard.py: which Bash commands the /research and /spec agents may run.

Each case runs the guard as its hook would: the command in the hook's JSON on stdin, exit 0 to
allow and exit 2 to block. Run with: python3 -m unittest discover -s ~/.claude/tests
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

GUARD = Path(__file__).resolve().parents[1] / "hooks" / "agent-guard.py"


def verdict(command):
    """(exit code, stderr) from the guard for one Bash command."""
    run = subprocess.run(
        [sys.executable, str(GUARD), "bash"],
        input=json.dumps({"tool_input": {"command": command}}),
        capture_output=True,
        text=True,
    )
    return run.returncode, run.stderr


class GuardTestCase(unittest.TestCase):
    def assertAllowed(self, command):
        code, err = verdict(command)
        self.assertEqual(code, 0, f"expected allowed: {command!r}\n{err}")

    def assertBlocked(self, command, mentions=None):
        code, err = verdict(command)
        self.assertEqual(code, 2, f"expected blocked: {command!r}")
        if mentions:
            self.assertIn(mentions, err)


class StillAllowed(GuardTestCase):
    """Commands the agents run today that must keep working."""

    def test_locale_prefix(self):
        self.assertAllowed("LC_ALL=C grep -o x f")

    def test_lowercase_shell_variable(self):
        self.assertAllowed('q=foo; curl -s "https://example.com/?q=$q"')

    def test_uppercase_shell_variable_not_exported(self):
        # Agents write these: F=<file>; grep ... $F and B=<url>; curl -s $B/...
        self.assertAllowed('F=notes.md; grep -n x "$F"')
        self.assertAllowed('B=https://example.com; curl -s "$B/x"')

    def test_gh_api_read(self):
        self.assertAllowed("gh api repos/o/r --jq .stargazers_count")

    def test_git_read(self):
        self.assertAllowed("git -C ~/notes diff HEAD~1 HEAD")

    def test_skill_script_by_path(self):
        self.assertAllowed("~/.claude/skills/research/scripts/check-note.py ~/notes/research/x.md")

    def test_env_wrapper_with_locale(self):
        self.assertAllowed("env LC_ALL=C sort f")

    def test_timezone_prefix(self):
        self.assertAllowed("TZ=UTC date")

    def test_for_loop_with_plain_variable(self):
        self.assertAllowed('for f in a b; do echo "$f"; done')

    def test_printf_to_plain_variable(self):
        self.assertAllowed("printf -v out '%s' x")


class ReadIsAReader(GuardTestCase):
    """`read` fills shell variables from input; it can't run programs or write files."""

    def test_while_read_loop(self):
        self.assertAllowed('while read -r line; do echo "$line"; done < f')

    def test_ifs_prefix_on_read(self):
        self.assertAllowed('while IFS= read -r line; do echo "$line"; done < f')

    def test_read_with_prompt_option(self):
        self.assertAllowed('read -r -p "name? " answer < f')


class AssignmentsBlocked(GuardTestCase):
    """Environment variables change what an allowed command runs, so they're blocked."""

    def test_git_external_diff_prefix(self):
        # git runs GIT_EXTERNAL_DIFF through a shell: this ran any command.
        self.assertBlocked("GIT_EXTERNAL_DIFF='echo hi' git diff", "GIT_EXTERNAL_DIFF")

    def test_git_external_diff_via_env(self):
        self.assertBlocked("env GIT_EXTERNAL_DIFF='echo hi' git diff", "GIT_EXTERNAL_DIFF")

    def test_bare_path(self):
        # PATH is exported, so a bare assignment changes it for every later command.
        self.assertBlocked("PATH=/tmp:$PATH; git status", "PATH")

    def test_bash_env_on_skill_script(self):
        self.assertBlocked(
            "BASH_ENV=f ~/.claude/skills/research/scripts/repo-health.sh o/r", "BASH_ENV"
        )

    def test_pythonpath_on_checker(self):
        self.assertBlocked(
            "PYTHONPATH=d python3 ~/.claude/skills/research/scripts/check-note.py n",
            "PYTHONPATH",
        )

    def test_curl_home(self):
        self.assertBlocked("CURL_HOME=d curl -s https://x", "CURL_HOME")

    def test_lowercase_proxy(self):
        self.assertBlocked("https_proxy=http://h curl -s https://x", "https_proxy")

    def test_bare_git_variable(self):
        self.assertBlocked("GIT_DIR=/x; git log", "GIT_DIR")

    def test_prefix_in_substitution(self):
        self.assertBlocked("echo $(GIT_EXTERNAL_DIFF='echo hi' git diff)", "GIT_EXTERNAL_DIFF")

    def test_prefix_in_bash_c(self):
        self.assertBlocked("bash -c \"GIT_EXTERNAL_DIFF='echo hi' git diff\"", "GIT_EXTERNAL_DIFF")

    def test_for_loop_over_path(self):
        self.assertBlocked("for PATH in /tmp; do git status; done", "PATH")

    def test_printf_into_path(self):
        self.assertBlocked("printf -v PATH '%s' /tmp; git status", "PATH")

    def test_ifs_prefix_on_other_command(self):
        self.assertBlocked("IFS=x grep y f", "IFS")


class StaysBlocked(GuardTestCase):
    """Blocked before this change, and must stay blocked."""

    def test_awk_runs_programs(self):
        self.assertBlocked("awk 'BEGIN{system(\"x\")}'")

    def test_read_into_path(self):
        self.assertBlocked("read -r PATH <<< x", "PATH")

    def test_export(self):
        self.assertBlocked("export GIT_EXTERNAL_DIFF=x")


if __name__ == "__main__":
    unittest.main()
