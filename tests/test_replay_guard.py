"""replay_guard.py judges recorded agent calls with the guard as it is now. These tests cover the
ways a replay can disagree with the run for reasons that aren't the guard's rules: the directory
one call ran in leaking into the next, and a run whose guard lived somewhere else (a plugin cache,
another checkout) being judged as if it lived in this one. Then main() itself, on a home
directory of made-up transcripts."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import replay_guard

REPO = Path(__file__).resolve().parents[1]
REPLAY = REPO / "tests" / "replay_guard.py"


class Replay(unittest.TestCase):
    def setUp(self):
        self.guard = replay_guard.load_guard(
            REPO / "hooks" / "agent-guard.py", "guard_under_test"
        )

    def test_a_read_does_not_change_the_directory_later_commands_run_in(self):
        before = self.guard.CWD
        replay_guard.read_verdict(
            self.guard, "Read", {"file_path": "x"}, "/somewhere/else"
        )
        self.assertEqual(self.guard.CWD, before)

    def test_a_cache_rooted_run_may_read_its_own_root_and_no_other(self):
        home = self.guard.HOME
        root = str(home / ".claude/plugins/cache/m/p/1.0.0")
        own = f"{root}/hooks/run-agent.sh"
        other = str(home / ".claude/plugins/cache/other/o/1.0.0/x")
        # Judged as a checkout's guard, the plugin cache is private.
        self.assertEqual(
            replay_guard.read_verdict(self.guard, "Read", {"file_path": own}, "/")[0],
            "blocked",
        )
        # Judged as the run's guard was, from its own root, its own files are readable...
        self.assertEqual(
            replay_guard.read_verdict(
                self.guard, "Read", {"file_path": own}, "/", None, root
            )[0],
            "allowed",
        )
        # ...and another plugin's still are not.
        self.assertEqual(
            replay_guard.read_verdict(
                self.guard, "Read", {"file_path": other}, "/", None, root
            )[0],
            "blocked",
        )
        self.assertIsNone(self.guard.OWN_ROOT)

    def test_a_root_outside_the_plugins_home_exempts_nothing(self):
        home = self.guard.HOME
        own = str(home / ".claude/plugins/cache/m/p/1.0.0/x")
        verdict = replay_guard.read_verdict(
            self.guard, "Read", {"file_path": own}, "/", None, "/some/checkout"
        )
        self.assertEqual(verdict[0], "blocked")

    def test_the_root_comes_from_the_run_dir_that_holds_the_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "name" / "spec-verifier"
            run.mkdir(parents=True)
            (run / "session_id").write_text("abc-123\n")
            hook = 'python3 "/r/plugins/cache/m/p/1/hooks/agent-guard.py" read'
            (run / "agents.json").write_text(json.dumps({"a": {"hooks": hook}}))
            old, replay_guard.RUNS = replay_guard.RUNS, Path(tmp)
            try:
                self.assertEqual(
                    replay_guard.guard_root(Path("/x/abc-123.jsonl")),
                    "/r/plugins/cache/m/p/1",
                )
                self.assertIsNone(replay_guard.guard_root(Path("/x/other.jsonl")))
            finally:
                replay_guard.RUNS = old

    def test_a_symlink_install_run_has_no_plugin_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "name" / "researcher"
            run.mkdir(parents=True)
            (run / "session_id").write_text("abc-123\n")
            hook = 'python3 "$HOME/.claude/hooks/agent-guard.py" bash'
            (run / "agents.json").write_text(json.dumps({"a": {"hooks": hook}}))
            old, replay_guard.RUNS = replay_guard.RUNS, Path(tmp)
            try:
                self.assertIsNone(replay_guard.guard_root(Path("/x/abc-123.jsonl")))
            finally:
                replay_guard.RUNS = old

    def test_an_old_install_script_is_judged_at_this_checkout(self):
        script = "research/scripts/repo-health.sh a/b"
        for home in ("~", "$HOME", "${HOME}", str(Path.home())):
            with self.subTest(home=home):
                command = f"{home}/.claude/skills/{script}"
                self.assertEqual(
                    replay_guard.plugin_spelling(command, None),
                    f"{REPO}/skills/{script}",
                )
                self.assertEqual(
                    replay_guard.plugin_spelling(command, "/r/p/1"),
                    f"{REPO}/skills/{script}",
                )
        # The recorded spelling was allowed then, and the plugin's spelling of it is allowed now.
        now = replay_guard.plugin_spelling(f"~/.claude/skills/{script}", None)
        self.assertEqual(replay_guard.verdict(self.guard, now)[0], "allowed")
        self.assertEqual(
            replay_guard.plugin_spelling("ls ~/.claude/projects", None),
            "ls ~/.claude/projects",
        )

    def test_a_run_under_another_root_is_judged_at_this_checkout(self):
        # The guard finds its scripts from its own location, so a run from another checkout, a
        # worktree or the plugin cache named scripts this checkout's guard wouldn't recognise.
        root = "/elsewhere/claude-skills"
        script = "skills/research/scripts/check-note.py note.md"
        moved = replay_guard.plugin_spelling(f"{root}/{script}", root)
        self.assertEqual(moved, f"{REPO}/{script}")
        self.assertEqual(replay_guard.verdict(self.guard, moved)[0], "allowed")
        # Only the root as a whole path: not a sibling it's the start of, nor a longer path.
        for other in (f"{root}-old/{script}", f"/x{root}/{script}"):
            with self.subTest(other=other):
                self.assertEqual(replay_guard.plugin_spelling(other, root), other)
        # A root under the home directory, however the command wrote the home.
        under_home = f"{Path.home()}/code/claude-skills"
        for home in ("~", "$HOME", "${HOME}", str(Path.home())):
            with self.subTest(home=home):
                self.assertEqual(
                    replay_guard.plugin_spelling(
                        f"{home}/code/claude-skills/{script}", under_home
                    ),
                    f"{REPO}/{script}",
                )


def transcript(*entries):
    return "".join(json.dumps(entry) + "\n" for entry in entries)


def refused(command_id, root):
    """The guard's reply, as a transcript records it, when it refused a Bash call."""
    reply = (
        f'PreToolUse:Bash hook error: [python3 "{root}/hooks/agent-guard.py" bash]: '
        "Blocked by agent-guard: `printenv` isn't on this agent's command list"
    )
    item = {
        "type": "tool_result",
        "tool_use_id": command_id,
        "is_error": True,
        "content": reply,
    }
    return {"type": "user", "message": {"content": [item]}}


def prompt(text):
    """The agent's prompt as the run saw it, which Claude Code saves in the transcript."""
    return {
        "type": "attachment",
        "attachment": {"type": "prompt_snapshot", "systemPrompt": [text]},
    }


class RootFromTheTranscript(unittest.TestCase):
    """A run dir keeps only its latest session, so an earlier session's root is found in its
    transcript: the guard names its own hook command when it refuses a call, and the
    researcher's prompt names the guard by path."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        old, replay_guard.RUNS = replay_guard.RUNS, self.dir / "runs"  # no run dirs
        self.addCleanup(setattr, replay_guard, "RUNS", old)

    def root(self, *entries):
        path = self.dir / "abc-123.jsonl"
        path.write_text(transcript(*entries))
        return replay_guard.guard_root(path)

    def test_the_guards_reply_names_the_root(self):
        self.assertEqual(self.root(refused("t1", "/r/c")), "/r/c")

    def test_the_researchers_prompt_names_the_root(self):
        text = "A hook (`/r/n/hooks/agent-guard.py`) enforces these rules."
        self.assertEqual(self.root(prompt(text)), "/r/n")

    def test_a_file_that_mentions_a_guard_is_not_the_root(self):
        item = {
            "type": "tool_result",
            "tool_use_id": "t1",
            "content": "/r/x/hooks/agent-guard.py",
        }
        self.assertIsNone(self.root({"type": "user", "message": {"content": [item]}}))

    def test_two_roots_or_the_symlink_install_give_none(self):
        self.assertIsNone(self.root(refused("t1", "/r/c"), refused("t2", "/r/d")))
        self.assertIsNone(self.root(refused("t1", "$HOME/.claude")))
        self.assertIsNone(self.root(prompt("run ~/.claude/hooks/agent-guard.py")))


def use(n, tool, **tool_input):
    """An agent's call `t<n>`, as a transcript records it."""
    item = {"type": "tool_use", "id": f"t{n}", "name": tool, "input": tool_input}
    return {"type": "assistant", "cwd": "/work", "message": {"content": [item]}}


class Main(unittest.TestCase):
    """replay_guard.py as the user runs it, with HOME a temporary directory that holds one
    headless researcher run: its line in sessions.log and its transcript. --base HEAD, because
    CI's checkout is shallow and the default base isn't in it."""

    SESSION = "11111111-2222-3333-4444-555555555555"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(os.path.realpath(tmp.name))
        runs = self.home / ".cache" / "agent-runs"
        runs.mkdir(parents=True)
        (runs / "sessions.log").write_text(
            f"2026-10-01T09:00:00Z researcher {self.SESSION}\n"
        )
        self.project = self.home / ".claude" / "projects" / "-work"
        self.project.mkdir(parents=True)

    def replay(self, *entries):
        """(exit code, output) of a replay of a transcript holding these entries."""
        (self.project / f"{self.SESSION}.jsonl").write_text(transcript(*entries))
        run = subprocess.run(
            [sys.executable, str(REPLAY), "--base", "HEAD"],
            capture_output=True,
            text=True,
            check=False,  # exit 1 is a verdict
            env={**os.environ, "HOME": str(self.home)},
        )
        return run.returncode, run.stdout + run.stderr

    def test_a_run_under_another_checkout_is_judged_at_this_one(self):
        # The run's guard lived at its own root and allowed its own script; the guard here would
        # refuse that path, which is no rule change.
        root = "/elsewhere/claude-skills"
        code, out = self.replay(
            use(
                0, "Bash", command=f"{root}/skills/research/scripts/check-note.py n.md"
            ),
            use(1, "Bash", command="printenv"),
            refused("t1", root),
        )
        self.assertEqual(code, 0, out)
        self.assertIn("verdict changed since they ran: 0", out)


if __name__ == "__main__":
    unittest.main()
