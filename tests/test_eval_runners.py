"""Tests for tests/agent-evals/run.sh and tests/skill-evals/run.sh: they exit 1 when a case fails,
0 only when every case passes, and 2 on a case that doesn't exist or when there are none. They
pass their caps, model and sandbox settings to claude, clean up their fixtures, and the skill runner
counts only this run's results.

A stub `claude` first on PATH prints a canned JSON result, so nothing is sent to a model. The
runners are pointed at fake cases in a temporary directory (EVAL_CASES), and write their results
there too (EVAL_OUT), not into the real results folders.
Run with: python3 -m unittest discover -s ~/code/github.com/claude-skills/tests
"""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
REPO = TESTS.parent
AGENT_RUN = TESTS / "agent-evals" / "run.sh"
SKILL_RUN = TESTS / "skill-evals" / "run.sh"
STUB = """#!/usr/bin/env python3
import json, os, re, sys
from pathlib import Path
with open(os.environ["STUB_ARGV"], "a") as f:
    f.write(json.dumps(sys.argv[1:]) + "\\n")
with open(os.environ["STUB_ARGV"] + ".model", "a") as f:
    f.write(os.environ.get("RUN_AGENT_MODEL", "<unset>") + "\\n")
with open(os.environ["STUB_ARGV"] + ".implement", "a") as f:
    f.write(os.environ.get("IMPLEMENT_MAX_USD", "<unset>") + "\\n")
# A skill that writes the eval note, leaves an agent run dir named after it, and changes another
# file in ~/notes, as a skill eval's research case might.
m = re.search(r"\\S*/eval-[^/\\s]*\\.md", sys.argv[-1])
if m and os.environ.get("STUB_SIDE_EFFECTS"):
    note = Path(m.group(0))
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("a note")
    run = Path.home() / ".cache/agent-runs" / note.stem / "researcher"
    run.mkdir(parents=True)
    (run / "reply.md").write_text("a reply")
    (Path.home() / "notes/other.md").write_text("an edit")
print(json.dumps({"subtype": "success", "is_error": False, "num_turns": 1,
                  "total_cost_usd": 0.01, "result": "the reply says yes"}))
"""


class Runners(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        (bin_dir / "claude").write_text(STUB)
        (bin_dir / "claude").chmod(0o755)
        self.cases = self.tmp / "cases"
        self.cases.mkdir()
        self.env = {
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "EVAL_CASES": str(self.cases),
            "EVAL_OUT": str(self.tmp / "out"),
            "STUB_ARGV": str(self.tmp / "argv.jsonl"),
        }
        for var in ("EVAL_MODEL", "RUN_AGENT_MODEL"):
            self.env.pop(var, None)

    def run_script(self, script, *cases):
        run = subprocess.run(
            [str(script), *cases],
            capture_output=True,
            text=True,
            env=self.env,
            check=False,
        )
        return run.returncode, run.stdout + run.stderr

    def argv(self):
        """The arguments of each claude call, in the order they were made."""
        path = self.tmp / "argv.jsonl"
        return (
            [json.loads(l) for l in path.read_text().splitlines()]
            if path.exists()
            else []
        )

    def flag(self, argv, name):
        return argv[argv.index(name) + 1] if name in argv else None

    def assertRendered(self, path, source):
        """`path` is the file agent-settings.py makes from `source` with the checkout as its
        root, written under this run's results: no runner passes a placeholder through."""
        self.assertTrue(path.startswith(str(self.tmp / "out")), path)
        text = Path(path).read_text()
        self.assertNotIn("${", text)
        rendered = subprocess.run(
            [str(REPO / "hooks" / "agent-settings.py"), str(source), str(REPO)],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        self.assertEqual(json.loads(text), json.loads(rendered))
        self.assertIn(f"{REPO}/skills/research/scripts/repo-health.sh *", text)

    def agent_case(self, name, expect):
        case = self.cases / name
        case.mkdir()
        (case / "agent.txt").write_text("cold-reviewer\n")
        (case / "brief.txt").write_text("a brief\n")
        (case / "expect.txt").write_text(expect)

    def skill_case(self, name, passes):
        case = self.cases / name
        case.mkdir()
        (case / "setup.sh").write_text("#!/bin/sh\nexit 0\n")
        (case / "prompt.txt").write_text("a prompt\n")
        (case / "grade.py").write_text(
            f"import sys\nprint('graded')\nsys.exit({0 if passes else 1})\n"
        )
        (case / "setup.sh").chmod(0o755)

    def test_agent_evals_pass(self):
        self.agent_case("good", "says yes\n")
        code, out = self.run_script(AGENT_RUN)
        self.assertEqual(code, 0, out)
        self.assertIn("1 of 1 passed", out)

    def test_agent_evals_fail(self):
        self.agent_case("good", "says yes\n")
        self.agent_case("bad", "says no\n")
        code, out = self.run_script(AGENT_RUN)
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL bad", out)
        self.assertIn("1 of 2 passed", out)

    def test_agent_evals_error_is_a_failure(self):
        self.agent_case("capped", "says yes\n")
        (self.tmp / "bin" / "claude").write_text(
            STUB.replace(
                '"success", "is_error": False',
                '"error_max_budget_usd", "is_error": True',
            )
        )
        code, out = self.run_script(AGENT_RUN)
        self.assertEqual(code, 1, out)
        self.assertIn("ERROR capped", out)

    def test_skill_evals_pass(self):
        self.skill_case("good", passes=True)
        code, out = self.run_script(SKILL_RUN)
        self.assertEqual(code, 0, out)
        self.assertIn("1 of 1 passed; total $0.01", out)

    def test_skill_evals_fail(self):
        self.skill_case("good", passes=True)
        self.skill_case("bad", passes=False)
        code, out = self.run_script(SKILL_RUN)
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL bad", out)
        self.assertIn("1 of 2 passed", out)

    def test_skill_evals_setup_failure_is_a_failure(self):
        self.skill_case("broken", passes=True)
        (self.cases / "broken" / "setup.sh").write_text("#!/bin/sh\nexit 1\n")
        code, out = self.run_script(SKILL_RUN)
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL broken (setup)", out)

    def test_unknown_case(self):
        for script in (AGENT_RUN, SKILL_RUN):
            with self.subTest(script=script.parent.name):
                code, out = self.run_script(script, "no-such-case")
                self.assertEqual(code, 2, out)

    def test_results_stay_out_of_the_real_folders(self):
        real = [TESTS / "skill-evals" / "results", TESTS / "agent-evals" / "results"]
        before = [sorted(p.iterdir()) if p.exists() else [] for p in real]
        self.skill_case("good", passes=True)
        self.agent_case("fine", "says yes\n")
        self.run_script(SKILL_RUN)
        self.run_script(AGENT_RUN)
        result = json.loads((self.tmp / "out" / "good.json").read_text())
        self.assertEqual(result["result"], "the reply says yes")
        self.assertEqual(
            [sorted(p.iterdir()) if p.exists() else [] for p in real], before
        )

    def test_agent_evals_pass_caps_and_sandbox(self):
        self.agent_case("plain", "says yes\n")
        self.agent_case("raised", "says yes\n")
        (self.cases / "raised" / "usd.txt").write_text("10\n")
        (self.cases / "raised" / "turns.txt").write_text("70\n")
        code, out = self.run_script(AGENT_RUN)
        self.assertEqual(code, 0, out)
        calls = self.argv()
        caps = sorted(
            (self.flag(a, "--max-budget-usd"), self.flag(a, "--max-turns"))
            for a in calls
        )
        self.assertEqual(caps, [("10", "70"), ("5", "40")])
        for argv in calls:
            self.assertEqual(self.flag(argv, "--setting-sources"), "user")
            self.assertRendered(
                self.flag(argv, "--settings"), REPO / "hooks" / "agent-sandbox.json"
            )
            self.assertIn("--strict-mcp-config", argv)
            self.assertEqual(self.flag(argv, "--agent"), "cold-reviewer")
            defs = json.loads(Path(self.flag(argv, "--agents")).read_text())
            self.assertEqual(list(defs), ["cold-reviewer"])
            self.assertEqual(self.flag(argv, "--allowedTools"), "Read,Grep,Glob,Bash")

    def test_agent_evals_agents_name_the_checkout_as_their_root(self):
        self.agent_case("plain", "says yes\n")
        self.run_script(AGENT_RUN)
        (argv,) = self.argv()
        text = Path(self.flag(argv, "--agents")).read_text()
        self.assertIn(f'python3 \\"{REPO}/hooks/agent-guard.py\\" bash', text)
        self.assertNotIn("${", text)
        self.assertIn(str(REPO), argv[argv.index("--add-dir") :])

    def test_agent_evals_settings_override(self):
        custom = self.tmp / "custom.json"
        custom.write_text('{"sandbox": {"excludedCommands": ["${CLAUDE_PLUGIN_ROOT}/x *"]}}')
        self.agent_case("plain", "says yes\n")
        self.env["EVAL_SETTINGS"] = str(custom)
        self.run_script(AGENT_RUN)
        (argv,) = self.argv()
        rendered = json.loads(Path(self.flag(argv, "--settings")).read_text())
        self.assertEqual(rendered, {"sandbox": {"excludedCommands": [f"{REPO}/x *"]}})
        # Set empty, it still passes no --settings.
        self.env["EVAL_SETTINGS"] = ""
        self.run_script(AGENT_RUN)
        self.assertNotIn("--settings", self.argv()[-1])

    def test_agent_eval_cap_override(self):
        self.agent_case("plain", "says yes\n")
        self.env["AGENT_EVAL_MAX_USD"] = "2"
        self.run_script(AGENT_RUN)
        (argv,) = self.argv()
        self.assertEqual(self.flag(argv, "--max-budget-usd"), "2")

    def test_skill_evals_pass_caps_and_sandbox(self):
        self.skill_case("good", passes=True)
        self.run_script(SKILL_RUN)
        self.env["SKILL_EVAL_MAX_USD"] = "1"
        self.run_script(SKILL_RUN)
        first, second = self.argv()
        self.assertEqual(self.flag(first, "--max-budget-usd"), "3")
        self.assertEqual(self.flag(second, "--max-budget-usd"), "1")
        self.assertEqual(self.flag(first, "--max-turns"), "60")
        self.assertRendered(
            self.flag(first, "--settings"), REPO / "hooks" / "agent-sandbox.json"
        )
        self.assertIn("--strict-mcp-config", first)

    def test_skill_evals_load_the_checkout_as_the_plugin(self):
        self.skill_case("good", passes=True)
        self.run_script(SKILL_RUN)
        (argv,) = self.argv()
        self.assertEqual(self.flag(argv, "--plugin-dir"), str(REPO))

    def test_skill_eval_prompts_type_the_namespaced_skill(self):
        # The bare /spec also resolves, but not to this plugin alone while an old install is present.
        for prompt in sorted((REPO / "tests" / "skill-evals" / "cases").glob("*/prompt.txt")):
            with self.subTest(case=prompt.parent.name):
                self.assertRegex(prompt.read_text(), r"\A/claude-skills:(spec|research|idea|cold-review|implement) ")

    def test_skill_evals_pass_the_model_to_the_skill_and_its_agents(self):
        self.skill_case("good", passes=True)
        self.env["RUN_AGENT_MODEL"] = "stale"
        self.run_script(SKILL_RUN)
        self.env["EVAL_MODEL"] = "sonnet"
        self.run_script(SKILL_RUN)
        default, chosen = self.argv()
        self.assertNotIn("--model", default)
        self.assertEqual(self.flag(chosen, "--model"), "sonnet")
        # RUN_AGENT_MODEL as the skill's session, and so run-agent.sh, sees it: a stale one in
        # the environment is cleared when no model is chosen.
        models = (self.tmp / "argv.jsonl.model").read_text().splitlines()
        self.assertEqual(models, ["", "sonnet"])

    def test_agent_evals_skip_a_case_for_another_model(self):
        self.agent_case("any", "says yes\n")
        self.agent_case("opus-only", "says yes\n")
        (self.cases / "opus-only" / "models.txt").write_text("opus\n")
        self.env["EVAL_MODEL"] = "sonnet"
        code, out = self.run_script(AGENT_RUN)
        self.assertEqual(code, 0, out)
        self.assertIn("SKIP opus-only: runs only on opus, not sonnet", out)
        self.assertIn("1 of 1 passed", out)
        self.assertEqual(len(self.argv()), 1)
        self.env["EVAL_MODEL"] = "opus"
        code, out = self.run_script(AGENT_RUN)
        self.assertIn("2 of 2 passed", out)
        self.env["EVAL_MODEL"] = "sonnet"
        code, out = self.run_script(AGENT_RUN, "opus-only")
        self.assertEqual(code, 0, out)
        self.assertIn("every case was skipped", out)

    def test_agent_evals_pass_the_model(self):
        self.agent_case("plain", "says yes\n")
        self.env["EVAL_MODEL"] = "opus"
        self.run_script(AGENT_RUN)
        (argv,) = self.argv()
        self.assertEqual(self.flag(argv, "--model"), "opus")

    def home(self):
        """A HOME of its own, with ~/notes a git repo, so no real ~/code or ~/notes is touched."""
        home = self.tmp.resolve() / "home"
        (home / "notes/research").mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(home / "notes")], check=True)
        self.env["HOME"] = str(home)
        return home

    def test_skill_evals_code_location(self):
        home = self.home()
        self.skill_case("good", passes=True)
        (self.cases / "good" / "location.txt").write_text("code\n")
        (self.cases / "good" / "setup.sh").write_text(
            f'#!/bin/sh\necho "$1" >> {self.tmp}/works\n'
        )
        code, out = self.run_script(SKILL_RUN)
        self.assertEqual(code, 0, out)
        (work,) = (self.tmp / "works").read_text().split()
        self.assertEqual(Path(work).parent, home / "code")
        self.assertRegex(Path(work).name, r"^eval-good-\d{8}-\d{6}$")
        self.assertFalse(Path(work).exists())

    def test_skill_evals_settings_file(self):
        self.skill_case("plain", passes=True)
        self.skill_case("agents", passes=True)
        (self.cases / "agents" / "settings.txt").write_text("agent-case-settings.json\n")
        self.run_script(SKILL_RUN)
        settings = sorted(self.flag(a, "--settings") for a in self.argv())
        self.assertNotEqual(settings[0], settings[1])
        for path in settings:
            text = Path(path).read_text()
            self.assertNotIn("${", text)
            # Only the agent case's settings exclude run-agent.sh from the sandbox.
            has_runner = f"{REPO}/hooks/run-agent.sh *" in text
            self.assertEqual(has_runner, "agents" in path, path)

    def test_skill_evals_note_snapshot_and_clean_up(self):
        home = self.home()
        self.skill_case("good", passes=True)
        (self.cases / "good" / "prompt.txt").write_text("Write {{NOTE}} ({{STAMP}}).\n")
        (self.cases / "good" / "grade.py").write_text(
            "import json, os\nfrom pathlib import Path\n"
            f"Path({str(self.tmp / 'graded.json')!r}).write_text(json.dumps({{\n"
            "    k: os.environ.get(k) for k in ('EVAL_NOTE', 'NOTES_BEFORE', 'NOTES_AFTER')}\n"
            "    | {'note there': Path(os.environ['EVAL_NOTE']).exists()}))\n"
        )
        self.env["STUB_SIDE_EFFECTS"] = "1"
        code, out = self.run_script(SKILL_RUN)
        self.assertEqual(code, 0, out)
        (argv,) = self.argv()
        graded = json.loads((self.tmp / "graded.json").read_text())
        note = Path(graded["EVAL_NOTE"])
        self.assertEqual(note.parent, home / "notes/research")
        self.assertRegex(note.name, r"^eval-good-(\d{8}-\d{6})\.md$")
        stamp = note.stem.removeprefix("eval-good-")
        self.assertEqual(argv[-1], f"Write {note} ({stamp}).")
        self.assertTrue(graded["note there"])
        # The eval note isn't a change; the other edit is.
        self.assertEqual(graded["NOTES_BEFORE"], "")
        self.assertEqual(graded["NOTES_AFTER"], "?? other.md")
        self.assertFalse(note.exists())
        self.assertEqual((self.tmp / "out/good.note.md").read_text(), "a note")
        self.assertEqual(list((home / ".cache/agent-runs").iterdir()), [])
        self.assertTrue(
            (self.tmp / "out/good.agent-runs" / note.stem / "researcher/reply.md").exists()
        )

    def test_skill_evals_keep_and_remove_implement_runs(self):
        # An implement case leaves a worktree beside its ~/code fixture, the implementer's run dir
        # and the verifier's scratch dirs, all named after the fixture: copied to the results,
        # then removed.
        home = self.home()
        self.skill_case("impl", passes=True)
        (self.cases / "impl" / "location.txt").write_text("code\n")
        (self.cases / "impl" / "setup.sh").write_text(
            "#!/bin/sh\n"
            'set -e\nname=$(basename "$1")\n'
            'mkdir -p "$1-worktrees/spec" && echo w > "$1-worktrees/spec/f"\n'
            'r="$HOME/.cache/implement-runs/$name--spec/implementer"\n'
            'mkdir -p "$r" && echo "{}" > "$r/run.json"\n'
            'v="$HOME/.cache/implement-verify/$name/spec/V1"\n'
            'mkdir -p "$v" && echo verdict > "$v/reply.md"\n'
            f'echo "$1" >> {self.tmp}/works\n'
        )
        code, out = self.run_script(SKILL_RUN, "impl")
        self.assertEqual(code, 0, out)
        (work,) = (self.tmp / "works").read_text().split()
        name = Path(work).name
        self.assertFalse(Path(work + "-worktrees").exists())
        self.assertEqual(list((home / ".cache/implement-runs").iterdir()), [])
        self.assertEqual(list((home / ".cache/implement-verify").iterdir()), [])
        runs = self.tmp / "out/impl.implement-runs"
        self.assertTrue((runs / f"{name}--spec/implementer/run.json").exists())
        verify = self.tmp / "out/impl.implement-verify"
        self.assertEqual((verify / name / "spec/V1/reply.md").read_text(), "verdict\n")

    def test_skill_evals_remove_a_leftover_worktree_on_exit(self):
        # A worktree dir the case's own clean-up never reached (an interrupted case) is removed
        # by the exit trap, like the fixture itself.
        home = self.home()
        self.skill_case("impl", passes=True)
        (self.cases / "impl" / "location.txt").write_text("code\n")
        # The grader is the last step before the case's own clean-up: it makes the leftover
        # after that clean-up has already run for everything the setup made.
        (self.cases / "impl" / "grade.py").write_text(
            "import sys\nfrom pathlib import Path\n"
            "w = Path(sys.argv[1] + '-worktrees') / 'late'\nw.mkdir(parents=True)\n"
            f"Path({str(self.tmp / 'late')!r}).write_text(str(w))\n"
        )
        code, out = self.run_script(SKILL_RUN, "impl")
        self.assertEqual(code, 0, out)
        late = Path((self.tmp / "late").read_text())
        self.assertEqual(late.parents[1], home / "code")
        self.assertFalse(late.parent.exists())

    def test_skill_evals_cap_the_implementer_unless_set(self):
        self.skill_case("good", passes=True)
        self.run_script(SKILL_RUN)
        self.env["IMPLEMENT_MAX_USD"] = "7"
        self.run_script(SKILL_RUN)
        caps = (self.tmp / "argv.jsonl.implement").read_text().splitlines()
        self.assertEqual(caps, ["5", "7"])

    def test_no_cases_is_an_error_not_a_crash(self):
        for script in (AGENT_RUN, SKILL_RUN):
            with self.subTest(script=script.parent.name):
                code, out = self.run_script(script)
                self.assertEqual(code, 2, out)
                self.assertIn("no cases in", out)
                self.assertNotIn("unbound variable", out)

    def test_skill_evals_count_only_this_runs_results(self):
        self.skill_case("good", passes=True)
        (self.tmp / "out").mkdir()
        (self.tmp / "out" / "stale.result").write_text("PASS\n")
        code, out = self.run_script(SKILL_RUN)
        self.assertEqual(code, 0, out)
        self.assertIn("1 of 1 passed", out)

    def test_fixtures_are_cleaned_up(self):
        self.skill_case("good", passes=True)
        (self.cases / "good" / "setup.sh").write_text(
            f'#!/bin/sh\necho "$1" >> {self.tmp}/works\n'
        )
        self.run_script(SKILL_RUN)
        (work,) = (self.tmp / "works").read_text().split()
        self.assertFalse(Path(work).exists())
        self.assertFalse(Path(work).parent.exists())  # the temp root too


if __name__ == "__main__":
    unittest.main()
