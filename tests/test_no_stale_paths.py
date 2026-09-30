"""No tracked file names the old symlink install's paths, the skills, hooks and agents directories
under ~/.claude, outside the dated documents and an explicit exempt list. The plugin finds its files
through its root, `${CLAUDE_PLUGIN_ROOT}` in the skills and its own location in the scripts, so a
reference to the old paths works only on a machine that still has the links.

Run with: python3 -m unittest discover -s ~/code/github.com/claude-skills/tests
"""

import re
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
# Any spelling: ~/, $HOME/, Path.home() / "...", or an absolute home path.
STALE = re.compile(r"\.claude/(skills|hooks|agents)(?![\w-])")
# Dated documents keep the paths they were written with (CLAUDE.md, Conventions).
DATED = ("docs/specs/", "records/", "CHANGELOG.md", "tests/agent-evals/BASELINE.md")
EXEMPT = {
    "tests/test_mine_sessions.py": "fixtures copied from session logs recorded under the old install",
    "tests/test_agent_def.py": "checks that no old path survives in an agent definition",
    "tests/test_run_agent.py": "checks that no old path survives in the runner's output",
    "tests/replay_guard.py": "moves recorded commands' old-install script paths to the plugin root",
    "tests/test_replay_guard.py": "checks that move, on old-install spellings",
    "tests/test_no_stale_paths.py": "its own examples of what is and isn't caught",
}


def tracked():
    """The tracked files, not a walk: that would also read the untracked tests/*/results/."""
    out = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "-z"], capture_output=True, text=True, check=True
    ).stdout
    return [p for p in out.split("\0") if p]


def stale_lines(paths, read):
    """`path:line: text` for each line that names an old path, in files neither dated nor exempt."""
    found = []
    for path in paths:
        if path.startswith(DATED) or path in EXEMPT:
            continue
        text = read(path)
        if text is None:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if STALE.search(line):
                found.append(f"{path}:{n}: {line.strip()}")
    return found


def read_repo_file(path):
    """The file's text, or None for a binary file or one deleted but not yet staged."""
    try:
        return (REPO / path).read_text()
    except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
        return None


class NoStalePaths(unittest.TestCase):
    def test_no_tracked_file_names_an_old_install_path(self):
        found = stale_lines(tracked(), read_repo_file)
        self.assertEqual(found, [], "old install paths; use the plugin root instead:\n" + "\n".join(found))

    def test_exempt_files_exist(self):
        # A renamed or deleted file must leave the list, or the exemption silently covers nothing.
        files = set(tracked())
        for path in EXEMPT:
            with self.subTest(path=path):
                self.assertIn(path, files)

    def test_every_spelling_is_caught(self):
        files = {
            "skills/x/SKILL.md": "run ~/.claude/skills/research/scripts/a.py\n",
            "hooks/x.sh": 'python3 "$HOME/.claude/hooks/agent-guard.py"\n',
            "tests/x.py": 'Path.home() / ".claude/agents/researcher.md"\n',
            "docs/x.md": "the agents live in /Users/u/.claude/agents\n",
        }
        self.assertEqual(len(stale_lines(files, files.get)), 4)

    def test_what_is_not_caught(self):
        files = {
            "skills/x/SKILL.md": "run ${CLAUDE_PLUGIN_ROOT}/skills/research/scripts/a.py\n",
            "hooks/x.md": "reads ~/.claude/plugins/cache and ~/.claude/projects\n",
            "tests/x.py": "the guard also denies ~/.claude/skills-backup\n",
            "docs/specs/2026-09-01-x.md": "linked ~/.claude/skills into the repo\n",
            "records/README-record.md": "- Not reviewed: ~/.claude/hooks\n",
            "CHANGELOG.md": "~/.claude/skills links\n",
            "tests/test_mine_sessions.py": "~/.claude/hooks/run-agent.sh\n",
        }
        self.assertEqual(stale_lines(files, files.get), [])


if __name__ == "__main__":
    unittest.main()
