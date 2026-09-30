"""replay_guard.py judges recorded agent calls with the guard as it is now. These tests cover the
two ways a replay can disagree with the run for reasons that aren't the guard's rules: the
directory one call ran in leaking into the next, and a run whose guard lived in a plugin cache
being judged as if it lived in a checkout."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import replay_guard  # noqa: E402

REPO = Path(__file__).resolve().parents[1]


class Replay(unittest.TestCase):
    def setUp(self):
        self.guard = replay_guard.load_guard(REPO / "hooks" / "agent-guard.py", "guard_under_test")

    def test_a_read_does_not_change_the_directory_later_commands_run_in(self):
        before = self.guard.CWD
        replay_guard.read_verdict(self.guard, "Read", {"file_path": "x"}, "/somewhere/else")
        self.assertEqual(self.guard.CWD, before)

    def test_a_cache_rooted_run_may_read_its_own_root_and_no_other(self):
        home = self.guard.HOME
        root = str(home / ".claude/plugins/cache/m/p/1.0.0")
        own = f"{root}/hooks/run-agent.sh"
        other = str(home / ".claude/plugins/cache/other/o/1.0.0/x")
        # Judged as a checkout's guard, the plugin cache is private.
        self.assertEqual(replay_guard.read_verdict(self.guard, "Read", {"file_path": own}, "/")[0], "blocked")
        # Judged as the run's guard was, from its own root, its own files are readable...
        self.assertEqual(
            replay_guard.read_verdict(self.guard, "Read", {"file_path": own}, "/", None, root)[0], "allowed"
        )
        # ...and another plugin's still are not.
        self.assertEqual(
            replay_guard.read_verdict(self.guard, "Read", {"file_path": other}, "/", None, root)[0], "blocked"
        )
        self.assertIsNone(self.guard.OWN_ROOT)

    def test_a_root_outside_the_plugins_home_exempts_nothing(self):
        home = self.guard.HOME
        own = str(home / ".claude/plugins/cache/m/p/1.0.0/x")
        verdict = replay_guard.read_verdict(self.guard, "Read", {"file_path": own}, "/", None, "/some/checkout")
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
                self.assertEqual(replay_guard.guard_root(Path("/x/abc-123.jsonl")), "/r/plugins/cache/m/p/1")
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

    def test_an_old_install_script_is_judged_at_the_plugin_root(self):
        script = "research/scripts/repo-health.sh a/b"
        for home in ("~", "$HOME", "${HOME}", str(Path.home())):
            with self.subTest(home=home):
                command = f"{home}/.claude/skills/{script}"
                self.assertEqual(replay_guard.plugin_spelling(command, None), f"{REPO}/skills/{script}")
                self.assertEqual(replay_guard.plugin_spelling(command, "/r/p/1"), f"/r/p/1/skills/{script}")
        # The recorded spelling was allowed then, and the plugin's spelling of it is allowed now.
        now = replay_guard.plugin_spelling(f"~/.claude/skills/{script}", None)
        self.assertEqual(replay_guard.verdict(self.guard, now)[0], "allowed")
        self.assertEqual(replay_guard.plugin_spelling("ls ~/.claude/projects", None), "ls ~/.claude/projects")


if __name__ == "__main__":
    unittest.main()
