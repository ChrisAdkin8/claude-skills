"""Tests for hooks/agent-settings.py, which prints a sandbox settings file with
${CLAUDE_PLUGIN_ROOT} replaced by the plugin root, and for the settings files it renders."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RENDER = REPO / "hooks" / "agent-settings.py"
FILES = {
    "agent-sandbox.json": REPO / "hooks" / "agent-sandbox.json",
    "agent-case-settings.json": REPO / "tests" / "skill-evals" / "agent-case-settings.json",
}
NET = ("repo-health.sh", "gcp-skus.sh", "reddit-search.sh")


def render(path, root):
    run = subprocess.run(
        [sys.executable, str(RENDER), str(path), str(root)],
        capture_output=True,
        text=True,
        check=False,
    )
    return run.returncode, run.stdout, run.stderr


class Renderer(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def settings(self, text):
        path = self.tmp / "s.json"
        path.write_text(text)
        return path

    def test_replaces_the_placeholder_with_the_root(self):
        path = self.settings('{"a": ["${CLAUDE_PLUGIN_ROOT}/x *", "y"]}')
        code, out, err = render(path, "/r/o o")
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out), {"a": ["/r/o o/x *", "y"]})

    def test_root_is_made_absolute(self):
        path = self.settings('{"a": "${CLAUDE_PLUGIN_ROOT}"}')
        code, out, err = render(path, ".")
        self.assertEqual(code, 0, err)
        self.assertTrue(json.loads(out)["a"].startswith("/"))

    def test_any_other_variable_is_refused(self):
        for text in ('{"a": "${HOME}/x"}', '{"a": "${CLAUDE_PLUGIN_DATA}"}', '{"a": "${}"}'):
            with self.subTest(text=text):
                code, out, err = render(self.settings(text), "/r")
                self.assertEqual(code, 2)
                self.assertEqual(out, "")
                self.assertIn("${", err)

    def test_bad_input_is_refused(self):
        self.assertEqual(render(self.tmp / "missing.json", "/r")[0], 2)
        self.assertEqual(render(self.settings("not json"), "/r")[0], 2)
        run = subprocess.run([sys.executable, str(RENDER)], capture_output=True, check=False)
        self.assertEqual(run.returncode, 2)


class RenderedSettings(unittest.TestCase):
    def test_committed_files_keep_the_placeholder_and_render_without_one(self):
        for name, path in FILES.items():
            with self.subTest(file=name):
                self.assertIn("${CLAUDE_PLUGIN_ROOT}", path.read_text())
                code, out, err = render(path, REPO)
                self.assertEqual(code, 0, err)
                self.assertNotIn("${", out)
                self.assertIn(str(REPO), out)

    def test_both_spellings_are_excluded_until_the_skills_move(self):
        for name, path in FILES.items():
            entries = json.loads(render(path, REPO)[1])["sandbox"]["excludedCommands"]
            for script in NET:
                for spelling in (f"{REPO}/skills/research/scripts", "~/.claude/skills/research/scripts"):
                    with self.subTest(file=name, entry=f"{spelling}/{script}"):
                        self.assertIn(f"{spelling}/{script} *", entries)
            self.assertIn("gh", entries)
        case = json.loads(render(FILES["agent-case-settings.json"], REPO)[1])
        entries = case["sandbox"]["excludedCommands"]
        self.assertIn(f"{REPO}/hooks/run-agent.sh *", entries)
        self.assertIn("~/.claude/hooks/run-agent.sh *", entries)
        base = json.loads(render(FILES["agent-sandbox.json"], REPO)[1])
        self.assertNotIn(f"{REPO}/hooks/run-agent.sh *", base["sandbox"]["excludedCommands"])


if __name__ == "__main__":
    unittest.main()
