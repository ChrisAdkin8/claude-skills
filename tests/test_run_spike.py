"""Tests for skills/spec/scripts/run-spike.sh: it launches claude only in a spike's own scratch
directory, laid out as prepare-spike.sh makes it, and with the spike's settings. And it refuses a
results.md, run.json or run.err that the spike left as a link, which /spec would follow.

A stub `claude` first on PATH records its arguments, so nothing is sent to a model. It can also
run a shell command in the scratch dir, as the spiker's Bash calls would. HOME is a temporary
directory reached through a symlink, as a home on another volume might be.
Run with: python3 -m unittest discover -s ~/code/github.com/claude-skills/tests
"""

import json
import os
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[1] / "skills" / "spec" / "scripts" / "run-spike.sh"
)
STUB = """#!/usr/bin/env python3
import json, os, subprocess, sys
# The launchers' version check (hooks/launch-checks.sh), answered before the call is logged.
if sys.argv[1:] == ["--version"]:
    print("2.1.285 (Claude Code)")
    sys.exit(0)
with open(os.environ["STUB_CALLS"], "a") as f:
    f.write(json.dumps({"argv": sys.argv[1:], "cwd": os.getcwd(),
                        "uv": os.environ.get("UV_CACHE_DIR"),
                        "memory": os.environ.get("CLAUDE_CODE_DISABLE_AUTO_MEMORY")}) + "\\n")
if os.environ.get("STUB_DOES"):
    subprocess.run(["/bin/sh", "-c", os.environ["STUB_DOES"]], check=True)
print(json.dumps({"result": "done"}))
sys.exit(int(os.environ.get("STUB_EXIT", "0")))
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
        # Unset here, so only the script can turn auto memory off.
        self.env.pop("CLAUDE_CODE_DISABLE_AUTO_MEMORY", None)

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
        # A copy of the spike's settings.json with the account override, beside the scratch dir
        # (hooks/launch-checks.sh; tests/test_launch_checks.py).
        copy = (self.root / "repo/spec/S1.settings.json").resolve()
        self.assertEqual(call["argv"][call["argv"].index("--settings") + 1], str(copy))
        self.assertEqual(
            json.loads(copy.read_text()),
            {"apiKeyHelper": "", "env": {"ANTHROPIC_API_KEY": ""}},
        )
        # $(cat) drops the newline. After `--`, so a brief that starts with a dash is never
        # read as an option.
        self.assertEqual(call["argv"][-2:], ["--", "the brief"])
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
        self.assertEqual(call["memory"], "1")  # no auto memory, as in run-agent.sh
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

    def spike_that_does(self, n, does, status=0):
        """Runs spike S<n>, whose stub runs `does` in the scratch dir and exits `status`."""
        path = self.scratch(f"repo/spec/S{n}")
        self.env["STUB_DOES"] = does
        self.env["STUB_EXIT"] = str(status)
        code, out = self.run_spike(path)
        return path, code, out

    def test_keeps_claudes_status_and_the_files_the_run_wrote(self):
        # The script waits for claude rather than exec-ing it, so claude's status still comes
        # through, and plain files stay for /spec to read.
        for n, status in enumerate((0, 1, 7), start=1):
            with self.subTest(status=status):
                path, code, out = self.spike_that_does(
                    n, "echo '# The question' > results.md", status
                )
                self.assertEqual(code, status, out)
                self.assertNotIn("run-spike:", out)
                self.assertEqual((path / "results.md").read_text(), "# The question\n")
                self.assertIn("done", (path / "run.json").read_text())

    def test_refuses_and_removes_a_planted_symlink(self):
        # The sandbox stops a spike reading ~/.ssh, but not linking to it from its scratch dir.
        # /spec's own session, which no sandbox stops, then reads these files and copies
        # results.md into a committed file.
        secret = self.tmp / "secret"
        secret.write_text("a secret\n")
        outside = self.tmp / "outside"
        outside.mkdir()
        (outside / "kept").write_text("kept\n")
        s, o = shlex.quote(str(secret)), shlex.quote(str(outside))
        cases = (
            (["results.md"], f"ln -s {s} results.md"),
            # claude's output still goes to the file the script opened, now unlinked.
            (["run.json"], f"rm run.json && ln -s {s} run.json"),
            (["run.err"], f"rm run.err && ln -s {s} run.err"),
            (["results.md"], "ln -s /nonexistent/key results.md"),  # to nothing
            (["results.md"], f"ln -s {o} results.md"),  # to a directory
            (
                ["results.md", "run.err"],
                f"ln -s {s} results.md && rm run.err && ln -s {s} run.err",
            ),
        )
        for n, (names, does) in enumerate(cases, start=1):
            with self.subTest(does=does):
                path, code, out = self.spike_that_does(n, does)
                self.assertEqual(code, 4, out)
                for name in names:
                    self.assertFalse(os.path.lexists(path / name), name)
                    self.assertIn(f"{name} was a symlink", out)
                # The spike chose the target, so it isn't repeated into /spec's session.
                for target in (str(secret), str(outside), "/nonexistent"):
                    self.assertNotIn(target, out)
        self.assertEqual(secret.read_text(), "a secret\n")
        self.assertEqual((outside / "kept").read_text(), "kept\n")

    def test_refuses_and_removes_what_isnt_a_regular_file(self):
        # A directory can hold links of its own, and a FIFO stalls whoever reads it.
        secret = self.tmp / "secret"
        secret.write_text("a secret\n")
        s = shlex.quote(str(secret))
        cases = (
            ("results.md", f"mkdir results.md && ln -s {s} results.md/key"),
            ("results.md", "mkfifo results.md"),
            ("run.json", "rm run.json && mkdir run.json"),
        )
        for n, (name, does) in enumerate(cases, start=1):
            with self.subTest(does=does):
                path, code, out = self.spike_that_does(n, does)
                self.assertEqual(code, 4, out)
                self.assertFalse(os.path.lexists(path / name), name)
                self.assertIn(f"{name} was not a regular file", out)
        self.assertEqual(secret.read_text(), "a secret\n")

    def test_refuses_a_link_when_claude_failed_too(self):
        # On any code but 4, /spec reads the files.
        secret = self.tmp / "secret"
        secret.write_text("a secret\n")
        path, code, out = self.spike_that_does(
            1, f"ln -s {shlex.quote(str(secret))} results.md", status=1
        )
        self.assertEqual(code, 4, out)
        self.assertFalse(os.path.lexists(path / "results.md"))

    def test_a_link_left_from_an_earlier_run_is_cleared_first(self):
        # The script writes run.json and run.err through a shell redirect, which would follow a
        # link that an earlier, refused run couldn't remove. And /spec reads results.md as this
        # run's, so an earlier one, link or not, goes too.
        secret = self.tmp / "secret"
        secret.write_text("a secret\n")
        path = self.scratch()
        for name in ("results.md", "run.json", "run.err"):
            (path / name).symlink_to(secret)
        code, out = self.run_spike(path)
        self.assertEqual(code, 0, out)
        self.assertEqual(secret.read_text(), "a secret\n")
        self.assertFalse(os.path.lexists(path / "results.md"))
        for name in ("run.json", "run.err"):
            self.assertFalse((path / name).is_symlink(), name)
        self.assertIn("done", (path / "run.json").read_text())

    @unittest.skipIf(os.geteuid() == 0, "root can remove it anyway")
    def test_refuses_to_start_over_a_link_it_cant_clear(self):
        # An earlier spike took away its scratch dir's write permission, so its link stays. The
        # run doesn't start, rather than write through it.
        secret = self.tmp / "secret"
        secret.write_text("a secret\n")
        path = self.scratch()
        (path / "run.json").symlink_to(secret)
        path.chmod(0o555)
        self.addCleanup(path.chmod, 0o755)
        code, out = self.run_spike(path)
        self.assertEqual(code, 2, out)
        self.assertIn("couldn't clear", out)
        self.assertEqual(secret.read_text(), "a secret\n")
        self.assertEqual(self.calls_made(), [])

    @unittest.skipIf(os.geteuid() == 0, "root can remove it anyway")
    def test_refuses_a_link_it_cant_remove(self):
        # A spike may take away its own scratch dir's write permission, so the link stays. Exit 4
        # still tells /spec not to read it.
        secret = self.tmp / "secret"
        secret.write_text("a secret\n")
        path = self.scratch()
        self.addCleanup(path.chmod, 0o755)
        self.env["STUB_DOES"] = (
            f"ln -s {shlex.quote(str(secret))} results.md && chmod a-w ."
        )
        code, out = self.run_spike(path)
        self.assertEqual(code, 4, out)
        self.assertIn("results.md was a symlink", out)
        self.assertIn("couldn't remove it", out)
        self.assertEqual(secret.read_text(), "a secret\n")


if __name__ == "__main__":
    unittest.main()
