"""Tests for skills/spec/scripts/run-spike.sh: it launches claude only in a spike's own scratch
directory, laid out as prepare-spike.sh makes it, and with the spike's settings.

A stub `claude` first on PATH records its arguments, so nothing is sent to a model. HOME is a
temporary directory reached through a symlink, as a home on another volume might be.
Run with: python3 -m unittest discover -s ~/code/github.com/claude-skills/tests
"""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[1] / "skills" / "spec" / "scripts" / "run-spike.sh"
)
STUB = """#!/usr/bin/env python3
import json, os, sys
with open(os.environ["STUB_CALLS"], "a") as f:
    f.write(json.dumps({"argv": sys.argv[1:], "cwd": os.getcwd(),
                        "uv": os.environ.get("UV_CACHE_DIR")}) + "\\n")
print(json.dumps({"result": "done"}))
"""


class RunSpike(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        real_home = self.tmp / "real-home"
        self.root = real_home / ".cache" / "spec-spikes"
        self.root.mkdir(parents=True)
        self.home = self.tmp / "home"
        self.home.symlink_to(real_home)
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        (bin_dir / "claude").write_text(STUB)
        (bin_dir / "claude").chmod(0o755)
        self.calls = self.tmp / "calls.jsonl"
        self.env = {
            **os.environ,
            "HOME": str(self.home),
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "STUB_CALLS": str(self.calls),
        }

    def scratch(self, rel="repo/spec/S1", files=("brief.md", "settings.json")):
        path = self.root / rel
        path.mkdir(parents=True, exist_ok=True)
        for name in files:
            (path / name).write_text(
                "{}\n" if name.endswith(".json") else "the brief\n"
            )
        return path

    def run_spike(self, path):
        run = subprocess.run(
            [str(SCRIPT), str(path)],
            capture_output=True,
            text=True,
            env=self.env,
            check=False,
        )
        return run.returncode, run.stdout + run.stderr

    def calls_made(self):
        if not self.calls.exists():
            return []
        return [json.loads(line) for line in self.calls.read_text().splitlines()]

    def test_runs_in_scratch_through_symlinked_home(self):
        self.scratch()
        code, out = self.run_spike(self.home / ".cache/spec-spikes/repo/spec/S1")
        self.assertEqual(code, 0, out)
        (call,) = self.calls_made()
        self.assertEqual(
            Path(call["cwd"]).resolve(), (self.root / "repo/spec/S1").resolve()
        )
        self.assertIn("--settings", call["argv"])
        self.assertEqual(
            call["argv"][call["argv"].index("--settings") + 1], "settings.json"
        )
        self.assertEqual(call["argv"][-1], "the brief")  # $(cat) drops the newline
        # The caps and containment the README promises: $2, 60 turns, no project settings,
        # writes only inside the scratch dir, no MCP servers.
        argv = call["argv"]
        flag = lambda name: argv[argv.index(name) + 1]
        self.assertEqual(flag("--max-budget-usd"), "2")
        self.assertEqual(flag("--max-turns"), "60")
        self.assertEqual(flag("--setting-sources"), "user")
        self.assertEqual(
            flag("--allowedTools"), "Read Grep Glob Bash Write(./**) Edit(./**)"
        )
        self.assertIn("--strict-mcp-config", argv)
        self.assertIn("--no-session-persistence", argv)
        # The spiker prompt is found beside the script, not under ~/.claude (this HOME has none).
        self.assertEqual(
            flag("--append-system-prompt-file"), str(SCRIPT.parents[1] / "spiker.md")
        )
        self.assertTrue(SCRIPT.parents[1].joinpath("spiker.md").is_file())
        self.assertTrue(call["uv"].endswith("/.cache/spec-spikes/.uv-cache"))
        self.assertIn("done", (self.root / "repo/spec/S1/run.json").read_text())

    def test_refuses_other_dirs(self):
        (self.root / ".uv-cache").mkdir()
        (self.tmp / "elsewhere").mkdir()
        for path in (
            self.root,
            self.root / ".uv-cache",
            self.scratch("repo/spec"),  # one level short
            self.scratch("repo/spec/S1/deeper"),
            self.scratch("repo/spec/notS1"),
            self.tmp / "elsewhere",
            self.root / "repo/spec/S9",  # missing
        ):
            with self.subTest(path=path):
                code, out = self.run_spike(path)
                self.assertEqual(code, 2, out)
        self.assertEqual(self.calls_made(), [])

    def test_refuses_missing_brief_or_settings(self):
        for files in (("brief.md",), ("settings.json",)):
            with self.subTest(files=files):
                path = self.scratch(f"repo/spec/S{len(files[0])}", files)
                code, out = self.run_spike(path)
                self.assertEqual(code, 2, out)
                self.assertIn("missing", out)
        self.assertEqual(self.calls_made(), [])


if __name__ == "__main__":
    unittest.main()
