"""Tests for skills/implement/SKILL.md: every git command /implement runs itself, outside
git-read.py, turns off the file watcher and hooks, and still matches a rule in its allowed-tools.

A `core.fsmonitor` command or a `post-commit` hook planted in the shared git dir from a linked
worktree runs on the next `git status` or commit in the main checkout (spike S5,
docs/specs/spikes/2026-10-02-implementer-sandbox-results.md). git-read.py turns both off for
reads; docs/specs/2026-10-02-implement-git-safeguard.md has /implement do the same for the
commands that change things.

Run with: python3 -m unittest discover -s tests
"""

import fnmatch
import os
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_skill_frontmatter import allowed_tools

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "skills" / "implement" / "SKILL.md"
FLAGS = "-c core.fsmonitor=false -c core.hooksPath=/dev/null"
# A backquoted command that starts with `git -C`. git-read.py's start with its own path, so they
# never match.
GIT_COMMAND = re.compile(r"`(git -C [^`]*)`")
BASH_RULE = re.compile(r"Bash\(([^)]*)\)")


def body(path):
    """The skill's text after its frontmatter."""
    lines = path.read_text().splitlines()
    return "\n".join(lines[lines.index("---", 1) + 1 :])


def git_commands(path):
    return GIT_COMMAND.findall(body(path))


class GitCommandsInTheSteps(unittest.TestCase):
    def test_every_git_command_turns_off_the_watcher_and_hooks(self):
        commands = git_commands(SKILL)
        # Gate status, worktree add (new and resume), the first add and commit, the evidence
        # add, commit and status, and the tool rules' own line: at least these.
        self.assertGreaterEqual(len(commands), 8, commands)
        for command in commands:
            with self.subTest(command=command):
                self.assertRegex(
                    command,
                    r"^git -C \S+ " + re.escape(FLAGS) + " ",
                    "write it git -C <dir> " + FLAGS + " …",
                )

    def test_every_git_command_is_pre_approved(self):
        rules = BASH_RULE.findall(allowed_tools(SKILL))
        self.assertTrue(rules)
        for command in git_commands(SKILL):
            with self.subTest(command=command):
                self.assertTrue(
                    any(fnmatch.fnmatchcase(command, rule) for rule in rules),
                    f"no Bash(...) rule in allowed-tools matches it: {rules}",
                )

    def test_the_tool_rules_say_to_keep_both_flags(self):
        rules = body(SKILL).split("**Tool calls.**", 1)[1].split("\n## ", 1)[0]
        self.assertIn(FLAGS, rules)
        self.assertIn("revert", rules)


class PlantedWatcherAndHook(unittest.TestCase):
    """A scratch repo's git dir gets a core.fsmonitor command and a post-commit hook, each
    writing a marker. status, add and commit, run with the flags as SKILL.md writes them, leave
    no marker; run without them, as a control, they leave both."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()
        self.env = {
            **os.environ,
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.com",
        }
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("commit", "-q", "--allow-empty", "-m", "first")
        self.fsmonitor_marker = self.tmp / "fsmonitor-ran"
        self.hook_marker = self.tmp / "post-commit-ran"
        watcher = self.tmp / "watcher"
        watcher.write_text(
            f"#!/bin/sh\ntouch {shlex.quote(str(self.fsmonitor_marker))}\nexit 1\n"
        )
        watcher.chmod(0o755)
        self.git("config", "core.fsmonitor", str(watcher))
        hook = self.repo / ".git" / "hooks" / "post-commit"
        hook.parent.mkdir(exist_ok=True)
        hook.write_text(f"#!/bin/sh\ntouch {shlex.quote(str(self.hook_marker))}\n")
        hook.chmod(0o755)

    def git(self, *args, flags=()):
        return subprocess.run(
            ["git", "-C", str(self.repo), *flags, *args],
            capture_output=True,
            text=True,
            check=True,
            env=self.env,
            timeout=60,
        ).stdout

    def status_add_commit(self, flags):
        (self.repo / "a.txt").write_text("a\n")
        self.git("status", "--porcelain", flags=flags)
        self.git("add", "a.txt", flags=flags)
        self.git("commit", "-q", "-m", "change", flags=flags)

    def test_with_the_flags_nothing_planted_runs(self):
        self.status_add_commit(FLAGS.split())
        self.assertFalse(self.fsmonitor_marker.exists(), "core.fsmonitor ran")
        self.assertFalse(self.hook_marker.exists(), "the post-commit hook ran")
        self.assertIn("change", self.git("log", "--oneline", flags=FLAGS.split()))

    def test_without_the_flags_both_run(self):
        # The control: the plant works, so the test above can see a missing flag.
        self.status_add_commit(())
        self.assertTrue(self.fsmonitor_marker.exists(), "core.fsmonitor didn't run")
        self.assertTrue(self.hook_marker.exists(), "the post-commit hook didn't run")


if __name__ == "__main__":
    unittest.main()
