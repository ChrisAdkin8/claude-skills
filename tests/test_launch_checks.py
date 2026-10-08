"""Tests for hooks/launch-checks.sh, through the six launchers that source it: hooks/run-agent.sh,
skills/spec/scripts/run-spike.sh, skills/implement/scripts/run-implementer.sh and run-verify.sh,
and both eval runners.

Each headless session runs on the user's Claude account, not on an ANTHROPIC_API_KEY that happens
to be set: the launcher unsets the key, says so in one line, and passes settings that switch off an
apiKeyHelper and a key in the user's settings' env block. CHECKED_PLANS_USE_API_KEY=1 keeps the
key, with no override and no note. A run that finds no account makes each plugin launcher exit 5
with the guidance to fix it.

A stub `claude` first on PATH records the key it was given and the settings it was passed, and
prints a result, so nothing is sent to a model. Everything runs under a home of its own.
Run with: python3 -m unittest discover -s tests
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUN_AGENT = REPO / "hooks" / "run-agent.sh"
RUN_SPIKE = REPO / "skills" / "spec" / "scripts" / "run-spike.sh"
RUN_IMPLEMENTER = REPO / "skills" / "implement" / "scripts" / "run-implementer.sh"
RUN_VERIFY = REPO / "skills" / "implement" / "scripts" / "run-verify.sh"
AGENT_EVALS = REPO / "tests" / "agent-evals" / "run.sh"
SKILL_EVALS = REPO / "tests" / "skill-evals" / "run.sh"
OVERRIDE = {"apiKeyHelper": "", "env": {"ANTHROPIC_API_KEY": ""}}
NOTE = "this run uses your Claude account, not ANTHROPIC_API_KEY"
NOT_LOGGED_IN = json.dumps(
    {
        "subtype": "success",
        "is_error": True,
        "result": "Not logged in · Please run /login",
    }
)
STUB = """#!/usr/bin/env python3
import json, os, sys
if sys.argv[1:] == ["--version"]:
    print(os.environ.get("STUB_VERSION", "2.1.285 (Claude Code)"))
    sys.exit(0)
argv = sys.argv[1:]
given = argv[argv.index("--settings") + 1] if "--settings" in argv else None
settings = path = None
if given is not None and given.lstrip().startswith("{"):
    settings = json.loads(given)
elif given is not None:
    path = os.path.abspath(given)
    settings = json.load(open(path))
with open(os.environ["STUB_CALLS"], "a") as f:
    f.write(json.dumps({"key": os.environ.get("ANTHROPIC_API_KEY"), "given": given,
                        "path": path, "settings": settings}) + "\\n")
print(os.environ.get("STUB_RESULT") or json.dumps(
    {"session_id": "sess-1", "subtype": "success", "is_error": False, "num_turns": 1,
     "total_cost_usd": 0.01, "result": os.environ.get("STUB_REPLY", "")}))
sys.exit(int(os.environ.get("STUB_EXIT", "0")))
"""


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@local", "-c", "user.name=t", *args],
        capture_output=True, text=True, check=True,
    ).stdout  # fmt: skip


def plugin_files():
    """Each file under the plugin's hooks/ and skills/, with its size and mtime: a launcher
    writes nothing there, the committed settings files included."""
    found = {}
    for top in (REPO / "hooks", REPO / "skills"):
        for path in top.rglob("*"):
            if "__pycache__" in path.parts or path.is_dir():
                continue
            st = path.lstat()
            found[str(path)] = (st.st_size, st.st_mtime_ns)
    return found


class LauncherCase(unittest.TestCase):
    """A home of its own and the four plugin launchers, set up to run under the stub."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        (bin_dir / "claude").write_text(STUB)
        (bin_dir / "claude").chmod(0o755)
        self.calls = self.tmp / "calls.jsonl"
        self.home = self.tmp / "home"
        (self.home / ".claude").mkdir(parents=True)
        self.env = {
            **os.environ,
            "HOME": str(self.home),
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "STUB_CALLS": str(self.calls),
            "RUN_AGENT_LOG": str(self.tmp / "sessions.log"),
            "ANTHROPIC_API_KEY": "dummy",
        }
        for var in (
            "CHECKED_PLANS_USE_API_KEY",
            "RUN_AGENT_MODEL",
            "IMPLEMENT_MAX_USD",
            "EVAL_MODEL",
            "EVAL_REPO",
            "EVAL_SETTINGS",
        ):
            self.env.pop(var, None)

    # Each launcher: what it needs in place, its arguments, the reply its shape check wants,
    # and the run folder whose settings copy sits beside it (or None).

    def run_agent(self):
        run = self.home / ".cache" / "agent-runs" / "proj" / "cold-reviewer"
        run.mkdir(parents=True)
        (run / "brief.md").write_text("Review this.\n")
        work = self.tmp / "work"
        work.mkdir(exist_ok=True)
        reply = "| # | Kind |\nCounts: 0 findings\nCold read: yes"
        return RUN_AGENT, ["cold-reviewer", work, run], reply, run / "settings.json"

    def run_spike(self):
        scratch = self.home / ".cache" / "spec-spikes" / "repo" / "spec" / "S1"
        scratch.mkdir(parents=True)
        (scratch / "brief.md").write_text("the brief\n")
        (scratch / "settings.json").write_text('{"sandbox": {"enabled": true}}\n')
        return RUN_SPIKE, [scratch], "done", scratch.parent / "S1.settings.json"

    def run_verify(self):
        scratch = self.home / ".cache" / "implement-verify" / "proj" / "spec" / "V1"
        (scratch / "src").mkdir(parents=True)
        for name in ("brief.md", "spec.md", "diff.patch"):
            (scratch / name).write_text("the brief\n")
        reply = "| W | Done when |\nVerified: 1 of 1\nImplementation holds: yes"
        return RUN_VERIFY, [scratch], reply, scratch.parent / "V1.settings.json"

    def run_implementer(self):
        repo = self.home / "code" / "proj"
        repo.mkdir(parents=True)
        git(repo, "init", "-q")
        (repo / "a.txt").write_text("a\n")
        git(repo, "add", "a.txt")
        git(repo, "commit", "-qm", "base")
        worktree = self.home / "code" / "proj-worktrees" / "spec"
        git(repo, "worktree", "add", "-q", str(worktree), "-b", "implement/spec")
        run = self.home / ".cache" / "implement-runs" / "proj--spec" / "implementer"
        run.mkdir(parents=True)
        (run / "brief.md").write_text("Implement it.\n")
        return (
            RUN_IMPLEMENTER,
            [worktree, run],
            "Implementer: done",
            run / "settings.json",
        )

    def plugin_launchers(self):
        return {
            "run-agent": self.run_agent,
            "run-spike": self.run_spike,
            "run-verify": self.run_verify,
            "run-implementer": self.run_implementer,
        }

    def launch(self, script, args, reply, **env):
        self.calls.unlink(missing_ok=True)
        run = subprocess.run(
            [str(script), *map(str, args)],
            capture_output=True,
            text=True,
            env={**self.env, "STUB_REPLY": reply, **env},
            check=False,
        )
        calls = (
            [json.loads(line) for line in self.calls.read_text().splitlines()]
            if self.calls.exists()
            else []
        )
        return run.returncode, run.stdout + run.stderr, calls

    def assertOverride(self, settings):
        self.assertEqual(settings["apiKeyHelper"], "")
        self.assertEqual(settings["env"]["ANTHROPIC_API_KEY"], "")

    def fresh_home(self):
        """A fresh home for the next launcher's setup, which makes the same paths."""
        shutil.rmtree(self.home)
        (self.home / ".claude").mkdir(parents=True)


class Launchers(LauncherCase):
    def test_plugin_launchers_run_on_the_account(self):
        before = plugin_files()
        for name, make in self.plugin_launchers().items():
            with self.subTest(launcher=name):
                script, args, reply, copy = make()
                code, out, calls = self.launch(script, args, reply)
                self.assertEqual(code, 0, out)
                (call,) = calls
                self.assertIsNone(call["key"])
                self.assertOverride(call["settings"])
                self.assertIn(f"{name}: {NOTE}", out)
                self.assertIn("CHECKED_PLANS_USE_API_KEY=1", out)
                # Where the copy is: the run dir's own, or beside the run's folder.
                self.assertEqual(call["path"], str(copy))
                self.assertTrue(copy.is_file() and not copy.is_symlink())
        # The source settings are rendered, and the spike's copied, but none is written over.
        self.assertEqual(plugin_files(), before)
        spike = self.home / ".cache" / "spec-spikes" / "repo" / "spec" / "S1"
        self.assertEqual(
            json.loads((spike / "settings.json").read_text()),
            {"sandbox": {"enabled": True}},
        )

    def test_the_copy_keeps_the_settings_it_was_made_from(self):
        script, args, reply, _ = self.run_spike()
        _, out, (call,) = self.launch(script, args, reply)
        self.assertEqual(call["settings"], {"sandbox": {"enabled": True}, **OVERRIDE})
        script, args, reply, _ = self.run_verify()
        _, out, (call,) = self.launch(script, args, reply)
        verify = json.loads(
            (REPO / "skills/implement/verify-settings.json").read_text()
        )
        self.assertEqual(call["settings"], {**verify, **OVERRIDE})

    def test_a_link_at_the_copys_name_is_replaced_not_followed(self):
        for name, make in self.plugin_launchers().items():
            with self.subTest(launcher=name):
                script, args, reply, copy = make()
                target = self.tmp / f"{name}-target.json"
                target.write_text('{"planted": true}\n')
                copy.parent.mkdir(parents=True, exist_ok=True)
                copy.symlink_to(target)
                code, out, (call,) = self.launch(script, args, reply)
                self.assertEqual(code, 0, out)
                self.assertEqual(target.read_text(), '{"planted": true}\n')
                self.assertFalse(copy.is_symlink())
                self.assertNotIn("planted", call["settings"])
                self.assertOverride(call["settings"])

    def test_the_opt_in_keeps_the_key(self):
        for name, make in self.plugin_launchers().items():
            with self.subTest(launcher=name):
                script, args, reply, _ = make()
                code, out, (call,) = self.launch(
                    script, args, reply, CHECKED_PLANS_USE_API_KEY="1"
                )
                self.assertEqual(code, 0, out)
                self.assertEqual(call["key"], "dummy")
                self.assertNotIn("apiKeyHelper", call["settings"])
                self.assertNotIn("env", call["settings"])
                self.assertNotIn(NOTE, out)

    def test_no_key_no_note(self):
        del self.env["ANTHROPIC_API_KEY"]
        for name, make in self.plugin_launchers().items():
            with self.subTest(launcher=name):
                script, args, reply, _ = make()
                code, out, (call,) = self.launch(script, args, reply)
                self.assertEqual(code, 0, out)
                self.assertNotIn(NOTE, out)
                self.assertOverride(call["settings"])

    def test_no_account_exits_5_with_the_guidance(self):
        for name, make in self.plugin_launchers().items():
            with self.subTest(launcher=name):
                script, args, reply, _ = make()
                code, out, calls = self.launch(
                    script, args, reply, STUB_RESULT=NOT_LOGGED_IN, STUB_EXIT="1"
                )
                self.assertEqual(code, 5, out)
                self.assertEqual(len(calls), 1)
                for words in (
                    "/login",
                    "claude setup-token",
                    "CLAUDE_CODE_OAUTH_TOKEN",
                    "CHECKED_PLANS_USE_API_KEY=1",
                ):
                    self.assertIn(words, out)

    def test_other_authentication_failures_exit_5(self):
        script, args, reply, _ = self.run_agent()
        for text in (
            "Failed to authenticate. API Error: 401 Invalid bearer token",
            "Invalid API key · Fix external API key",
            "Login expired · Please run /login",
        ):
            with self.subTest(text=text):
                result = json.dumps(
                    {"subtype": "success", "is_error": True, "result": text}
                )
                code, out, _ = self.launch(
                    script, args, reply, STUB_RESULT=result, STUB_EXIT="1"
                )
                self.assertEqual(code, 5, out)
        # Not an account failure: an error that says something else is claude's own exit.
        result = json.dumps(
            {"subtype": "success", "is_error": True, "result": "Request timed out"}
        )
        code, out, _ = self.launch(
            script, args, reply, STUB_RESULT=result, STUB_EXIT="1"
        )
        self.assertEqual(code, 1, out)
        # Nor is a reply that only mentions it.
        result = json.dumps(
            {
                "subtype": "success",
                "is_error": False,
                "result": "Not logged in? " + reply,
            }
        )
        code, out, _ = self.launch(script, args, reply, STUB_RESULT=result)
        self.assertEqual(code, 0, out)


class Version(LauncherCase):
    """Each launcher checks `claude --version` once, before anything else, and refuses below
    2.1.277, the version the sandbox rule holds from."""

    def test_an_old_claude_is_refused_before_any_call(self):
        for version in ("2.1.276 (Claude Code)", "2.0.999", "1.9.300 (Claude Code)"):
            for name, make in self.plugin_launchers().items():
                with self.subTest(launcher=name, version=version):
                    script, args, reply, copy = make()
                    code, out, calls = self.launch(
                        script, args, reply, STUB_VERSION=version
                    )
                    self.assertEqual(code, 2, out)
                    self.assertIn(
                        f"needs Claude Code 2.1.277 or later; this is {version}", out
                    )
                    self.assertEqual(calls, [])
                    # Before anything else: no settings were written.
                    self.assertFalse(copy.exists())
                self.fresh_home()

    def test_an_unreadable_version_is_refused(self):
        for version in ("", "Claude Code", "v2.1.285", "2.1.x"):
            for name, make in self.plugin_launchers().items():
                with self.subTest(launcher=name, version=version):
                    script, args, reply, _ = make()
                    code, out, calls = self.launch(
                        script, args, reply, STUB_VERSION=version
                    )
                    self.assertEqual(code, 2, out)
                    self.assertIn("needs Claude Code 2.1.277 or later; this is", out)
                    self.assertEqual(calls, [])
                self.fresh_home()

    def test_a_current_claude_carries_on(self):
        for version in (
            "2.1.277 (Claude Code)",
            "2.1.285 (Claude Code)",
            "2.2.0",
            "3.0.1",
        ):
            for name, make in self.plugin_launchers().items():
                with self.subTest(launcher=name, version=version):
                    script, args, reply, _ = make()
                    code, out, calls = self.launch(
                        script, args, reply, STUB_VERSION=version
                    )
                    self.assertEqual(code, 0, out)
                    self.assertEqual(len(calls), 1)
                    self.assertNotIn("needs Claude Code", out)
                self.fresh_home()

    def test_the_eval_runners_refuse_an_old_claude_too(self):
        cases = self.tmp / "cases"
        (cases / "plain").mkdir(parents=True)
        for script in (AGENT_EVALS, SKILL_EVALS):
            with self.subTest(runner=script.parent.name):
                code, out, calls = self.launch(
                    script,
                    [],
                    "",
                    STUB_VERSION="2.1.276 (Claude Code)",
                    EVAL_CASES=str(cases),
                    EVAL_OUT=str(self.tmp / "out"),
                )
                self.assertEqual(code, 2, out)
                self.assertIn("needs Claude Code 2.1.277 or later", out)
                self.assertEqual(calls, [])


class EvalRunners(unittest.TestCase):
    """Both eval runners unset the key and pass the override too, on their rendered copies; the
    agent runner with EVAL_SETTINGS empty passes the override alone."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        (bin_dir / "claude").write_text(STUB)
        (bin_dir / "claude").chmod(0o755)
        self.calls = self.tmp / "calls.jsonl"
        self.cases = self.tmp / "cases"
        self.cases.mkdir()
        self.env = {
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "EVAL_CASES": str(self.cases),
            "EVAL_OUT": str(self.tmp / "out"),
            "STUB_CALLS": str(self.calls),
            "STUB_REPLY": "the reply says yes",
            "ANTHROPIC_API_KEY": "dummy",
        }
        for var in (
            "CHECKED_PLANS_USE_API_KEY",
            "EVAL_MODEL",
            "EVAL_REPO",
            "EVAL_SETTINGS",
            "RUN_AGENT_MODEL",
        ):
            self.env.pop(var, None)

    def agent_case(self):
        case = self.cases / "agent" / "plain"
        case.mkdir(parents=True)
        (case / "agent.txt").write_text("cold-reviewer\n")
        (case / "brief.txt").write_text("a brief\n")
        (case / "expect.txt").write_text("says yes\n")

    def skill_case(self):
        case = self.cases / "skill" / "good"
        case.mkdir(parents=True)
        (case / "setup.sh").write_text("#!/bin/sh\nexit 0\n")
        (case / "setup.sh").chmod(0o755)
        (case / "prompt.txt").write_text("a prompt\n")
        (case / "grade.py").write_text("print('graded')\n")

    def launch(self, script, **env):
        self.calls.unlink(missing_ok=True)
        kind = "agent" if script == AGENT_EVALS else "skill"
        run = subprocess.run(
            [str(script)],
            capture_output=True,
            text=True,
            env={**self.env, "EVAL_CASES": str(self.cases / kind), **env},
            check=False,
        )
        out = run.stdout + run.stderr
        self.assertEqual(run.returncode, 0, out)
        (call,) = [json.loads(line) for line in self.calls.read_text().splitlines()]
        return call, out

    def test_both_runners_run_on_the_account(self):
        self.agent_case()
        self.skill_case()
        for script in (AGENT_EVALS, SKILL_EVALS):
            with self.subTest(runner=script.parent.name):
                call, _ = self.launch(script)
                self.assertIsNone(call["key"])
                self.assertEqual(call["settings"]["apiKeyHelper"], "")
                self.assertEqual(call["settings"]["env"]["ANTHROPIC_API_KEY"], "")
                self.assertIn("sandbox", call["settings"])
                self.assertTrue(call["path"].startswith(str(self.tmp / "out")))
                call, _ = self.launch(script, CHECKED_PLANS_USE_API_KEY="1")
                self.assertEqual(call["key"], "dummy")
                self.assertNotIn("apiKeyHelper", call["settings"])
                self.assertNotIn("env", call["settings"])

    def test_agent_runner_with_no_settings_passes_the_override_alone(self):
        self.agent_case()
        call, _ = self.launch(AGENT_EVALS, EVAL_SETTINGS="")
        self.assertIsNone(call["key"])
        self.assertIsNone(call["path"])
        self.assertEqual(call["settings"], OVERRIDE)
        call, _ = self.launch(
            AGENT_EVALS, EVAL_SETTINGS="", CHECKED_PLANS_USE_API_KEY="1"
        )
        self.assertEqual(call["key"], "dummy")
        self.assertIsNone(call["given"])


class Shellcheck(unittest.TestCase):
    def test_the_shared_file_says_its_shell(self):
        text = (REPO / "hooks" / "launch-checks.sh").read_text()
        self.assertTrue(text.startswith("# shellcheck shell=bash\n"))

    def test_every_launcher_sources_it_with_a_directive(self):
        for script in (
            RUN_AGENT,
            RUN_SPIKE,
            RUN_IMPLEMENTER,
            RUN_VERIFY,
            AGENT_EVALS,
            SKILL_EVALS,
        ):
            with self.subTest(script=script.name):
                lines = script.read_text().splitlines()
                (i,) = [
                    n
                    for n, l in enumerate(lines)
                    if "launch-checks.sh" in l
                    and l.lstrip().startswith(("source ", ". "))
                ]
                self.assertTrue(
                    lines[i - 1].lstrip().startswith("# shellcheck source=")
                )


if __name__ == "__main__":
    unittest.main()
