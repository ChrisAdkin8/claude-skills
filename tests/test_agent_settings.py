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
    "agent-case-settings.json": REPO
    / "tests"
    / "skill-evals"
    / "agent-case-settings.json",
}
NET = ("repo-health.sh", "gcp-skus.sh", "reddit-search.sh")


def render(path, root, *variables):
    run = subprocess.run(
        [sys.executable, str(RENDER), str(path), str(root), *variables],
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
        for text in (
            '{"a": "${HOME}/x"}',
            '{"a": "${CLAUDE_PLUGIN_DATA}"}',
            '{"a": "${}"}',
        ):
            with self.subTest(text=text):
                code, out, err = render(self.settings(text), "/r")
                self.assertEqual(code, 2)
                self.assertEqual(out, "")
                self.assertIn("${", err)

    def test_named_variables_are_replaced(self):
        path = self.settings('{"a": ["${X}/c", "${CLAUDE_PLUGIN_ROOT}/d"]}')
        code, out, err = render(path, "/r", "X=/a b")
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out), {"a": ["/a b/c", "/r/d"]})

    def test_a_variable_with_no_value_given_is_refused(self):
        path = self.settings('{"a": ["${X}/c", "${Y}"]}')
        code, out, err = render(path, "/r", "X=/a")
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("${Y}", err)

    def test_a_malformed_variable_argument_is_refused(self):
        path = self.settings('{"a": "b"}')
        for arg in ("x=1", "X", "=1", "1X=1"):
            with self.subTest(arg=arg):
                code, out, err = render(path, "/r", arg)
                self.assertEqual(code, 2)
                self.assertEqual(out, "")

    def test_bad_input_is_refused(self):
        self.assertEqual(render(self.tmp / "missing.json", "/r")[0], 2)
        self.assertEqual(render(self.settings("not json"), "/r")[0], 2)
        run = subprocess.run(
            [sys.executable, str(RENDER)], capture_output=True, check=False
        )
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

    def test_the_implementer_settings_render_with_the_runs_variables(self):
        path = REPO / "skills" / "implement" / "implementer-settings.json"
        names = ("WORKTREE", "GIT_DIR", "COMMON_DIR", "SCRATCH", "TMP")
        self.assertEqual(render(path, REPO)[0], 2)
        code, out, err = render(path, REPO, *(f"IMPLEMENT_{n}=/v/{n}" for n in names))
        self.assertEqual(code, 0, err)
        self.assertNotIn("${", out)
        for name in names:
            self.assertIn(f"/v/{name}", out)

    def test_the_network_scripts_are_excluded_by_the_roots_spelling(self):
        for name, path in FILES.items():
            entries = json.loads(render(path, REPO)[1])["sandbox"]["excludedCommands"]
            for script in NET:
                entry = f"{REPO}/skills/research/scripts/{script} *"
                with self.subTest(file=name, entry=entry):
                    self.assertIn(entry, entries)
                self.assertFalse([e for e in entries if e.startswith("~")], entries)
            self.assertIn("gh", entries)
        case = json.loads(render(FILES["agent-case-settings.json"], REPO)[1])
        entries = case["sandbox"]["excludedCommands"]
        self.assertIn(f"{REPO}/hooks/run-agent.sh *", entries)
        base = json.loads(render(FILES["agent-sandbox.json"], REPO)[1])
        self.assertNotIn(
            f"{REPO}/hooks/run-agent.sh *", base["sandbox"]["excludedCommands"]
        )


if __name__ == "__main__":
    unittest.main()
