"""Tests for tests/agent-evals/run.sh and tests/skill-evals/run.sh: they exit 1 when a case fails,
0 only when every case passes, and 2 on a case that doesn't exist or when there are none. They
pass their caps, model and sandbox settings to claude, clean up their fixtures, and the skill runner
counts only this run's results. The agent runner keeps the answer keys out of the agents' reach:
{{CASE}} is a copy of the fixture alone, {{REPO}} a clone without them, and the settings deny reads
of the checkout's copies. The skill runner pre-approves only the Skill tool and fails a case with a
denied call.

VerifierAnswers checks the verifier cases' expect.txt pass a sound reply and fail one that rules
every true claim WRONG. Graders runs the skill-eval graders on fixtures their own setup.sh builds:
a broken run must fail, and a sound one pass.

A stub `claude` first on PATH prints a canned JSON result, so nothing is sent to a model. The
runners are pointed at fake cases in a temporary directory (EVAL_CASES), and write their results
there too (EVAL_OUT), not into the real results folders.
Run with: python3 -m unittest discover -s ~/code/github.com/claude-skills/tests
"""

import json
import os
import re
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
with open(os.environ["STUB_ARGV"] + ".memory", "a") as f:
    f.write(os.environ.get("CLAUDE_CODE_DISABLE_AUTO_MEMORY", "<unset>") + "\\n")
with open(os.environ["STUB_ARGV"] + ".agent-usd", "a") as f:
    f.write(os.environ.get("RUN_AGENT_MAX_USD", "<unset>") + "\\n")
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
# An agent's view, kept for the test to look at after the runner has cleaned up: a copy of the
# directories the brief's `Case:` and `Repo:` lines name, as the agent would find them.
if os.environ.get("STUB_SNAPSHOT"):
    import shutil
    snap = Path(os.environ["STUB_SNAPSHOT"])
    named = dict(re.findall(r"(?m)^(Case|Repo): (\\S+)$", sys.argv[-1]))
    for key, path in named.items():
        shutil.copytree(path, snap / key.lower(), symlinks=True)
    (snap / "paths.json").write_text(json.dumps(named))
print(json.dumps({"subtype": "success", "is_error": False, "num_turns": 1,
                  "total_cost_usd": 0.01, "result": "the reply says yes",
                  "permission_denials": json.loads(os.environ.get("STUB_DENIALS", "[]"))}))
"""
# The answer key the F7a tests plant, and look for where an agent could reach it.
KEY = "ANSWER-KEY-7f3a"


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
        for var in (
            "EVAL_MODEL",
            "EVAL_REPO",
            "RUN_AGENT_MODEL",
            "RUN_AGENT_MAX_USD",
            "CLAUDE_CODE_DISABLE_AUTO_MEMORY",
        ):
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

    def add_dirs(self, argv):
        """The directories after --add-dir, up to the next option."""
        dirs = []
        for arg in argv[argv.index("--add-dir") + 1 :]:
            if arg.startswith("--"):
                break
            dirs.append(arg)
        return dirs

    def git(self, repo, *args):
        return subprocess.run(
            ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
        ).stdout

    def fixture_repo(self):
        """A repo for EVAL_REPO with answer keys in its tree and its history: the read-at commit
        holds an expect.txt, a note-expect.txt and BASELINE.md naming KEY, and the next commit
        changes the expect.txt and the code. Returns the repo and the read-at commit."""
        repo = self.tmp / "fixture-repo"
        files = {
            "hooks/guard.py": "def unwrap(argv):\n    return argv\n",
            "tests/test_guard.py": "import unittest\n",
            "tests/agent-evals/run.sh": "#!/bin/sh\n",
            "tests/agent-evals/BASELINE.md": f"The decoy is {KEY}-baseline.\n",
            "tests/agent-evals/cases/old/expect.txt": f"{KEY}-old\n",
            "tests/agent-evals/cases/old/note-expect.txt": f"{KEY}-note\n",
            "tests/agent-evals/cases/old/spec.md": "a fixture spec\n",
            "tests/skill-evals/cases/s/grade.py": "print('graded')\n",
        }
        for path, text in files.items():
            (repo / path).parent.mkdir(parents=True, exist_ok=True)
            (repo / path).write_text(text)
        g = ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t"]
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run([*g, "add", "."], check=True)
        subprocess.run([*g, "commit", "-qm", "read-at"], check=True)
        read_at = self.git(repo, "rev-parse", "HEAD").strip()
        (repo / "tests/agent-evals/cases/old/expect.txt").write_text(f"{KEY}-new\n")
        (repo / "hooks/guard.py").write_text("def unwrap(argv):\n    return argv[1:]\n")
        subprocess.run([*g, "commit", "-qam", "later"], check=True)
        return repo, read_at

    def snapshot_case(self, name="look"):
        """An agent case whose brief names {{CASE}} and {{REPO}}, run with the stub keeping a copy
        of both. Returns the directory the copies land in, as case/ and repo/, with paths.json
        holding the paths the brief gave."""
        case = self.cases / name
        case.mkdir()
        (case / "agent.txt").write_text("cold-reviewer\n")
        (case / "brief.txt").write_text("Case: {{CASE}}\nRepo: {{REPO}}\n")
        (case / "expect.txt").write_text(f"says yes\n# {KEY}-case\n")
        snap = self.tmp / "snap"
        self.env["STUB_SNAPSHOT"] = str(snap)
        return snap

    def assertRendered(self, path, source, overlay=False):
        """`path` is the file agent-settings.py makes from `source` with the checkout as its
        root, written under this run's results: no runner passes a placeholder through. With
        `overlay`, the agent runner's read denies follow the file's own, which come first and
        unchanged (test_agent_evals_settings_deny_the_answer_keys checks what they are)."""
        self.assertTrue(path.startswith(str(self.tmp / "out")), path)
        text = Path(path).read_text()
        self.assertNotIn("${", text)
        rendered = json.loads(
            subprocess.run(
                [str(REPO / "hooks" / "agent-settings.py"), str(source), str(REPO)],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
        )
        settings = json.loads(text)
        if overlay:
            fs, base_fs = (
                settings["sandbox"]["filesystem"],
                rendered["sandbox"]["filesystem"],
            )
            deny, base_deny = (
                settings["permissions"]["deny"],
                rendered["permissions"]["deny"],
            )
            self.assertGreater(len(fs["denyRead"]), len(base_fs["denyRead"]))
            self.assertGreater(len(deny), len(base_deny))
            fs["denyRead"] = fs["denyRead"][: len(base_fs["denyRead"])]
            settings["permissions"]["deny"] = deny[: len(base_deny)]
        self.assertEqual(settings, rendered)
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
                self.flag(argv, "--settings"),
                REPO / "hooks" / "agent-sandbox.json",
                overlay=True,
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
        # The guard and scripts run from the checkout, but the agent works in a clone of it
        # (test_agent_evals_repo_is_a_clone_without_the_answer_keys): the checkout, whose
        # tests/agent-evals holds the answer keys, isn't one of its directories.
        self.assertNotIn(str(REPO), self.add_dirs(argv))
        self.assertEqual(
            self.add_dirs(argv)[:2], [f"{Path.home()}/.claude", f"{Path.home()}/notes"]
        )

    def test_agent_evals_case_is_a_copy_of_the_fixture_alone(self):
        # {{CASE}} is a copy of the fixture files the brief needs: never the answer key or the
        # runner's other files, and under a name that doesn't give the case away.
        snap = self.snapshot_case("spec-miscite")
        case = self.cases / "spec-miscite"
        (case / "note-expect.txt").write_text(f"{KEY}-note\n")
        (case / "turns.txt").write_text("40\n")
        (case / "usd.txt").write_text("5\n")
        (case / "models.txt").write_text("opus\n")
        (case / "spec.md").write_text("the spec\n")
        (case / "records").mkdir()
        (case / "records/spec-record.md").write_text("its record\n")
        code, out = self.run_script(AGENT_RUN)
        self.assertEqual(code, 0, out)
        copy = snap / "case"
        files = sorted(str(p.relative_to(copy)) for p in copy.rglob("*") if p.is_file())
        self.assertEqual(files, ["records/spec-record.md", "spec.md"])
        self.assertFalse(any(KEY in (copy / f).read_text() for f in files))
        named = json.loads((snap / "paths.json").read_text())
        self.assertNotIn("spec-miscite", named["Case"])
        self.assertNotIn(str(self.cases), named["Case"])
        (argv,) = self.argv()
        self.assertIn(named["Case"], self.add_dirs(argv))
        self.assertFalse(Path(named["Case"]).exists())

    def test_agent_evals_repo_is_a_clone_without_the_answer_keys(self):
        repo, read_at = self.fixture_repo()
        self.env["EVAL_REPO"] = str(repo)
        snap = self.snapshot_case()
        code, out = self.run_script(AGENT_RUN)
        self.assertEqual(code, 0, out)
        clone = snap / "repo"
        # Neither reading files nor a plain `git grep` finds a key: the eval directories are gone
        # from the working tree and the index, and the rest of the tree is there.
        self.assertEqual(
            sorted(p.name for p in (clone / "tests").iterdir()), ["test_guard.py"]
        )
        self.assertEqual(self.git(clone, "grep", "-e", KEY), "")
        self.assertEqual(self.git(clone, "grep", "--cached", "-e", KEY), "")
        # Nor does the history: every expect.txt, note-expect.txt and BASELINE.md reads as empty.
        commits = self.git(clone, "rev-list", "--all").split()
        self.assertEqual(len(commits), 2)
        self.assertEqual(self.git(clone, "grep", "-e", KEY, *commits), "")
        self.assertNotIn(KEY, self.git(clone, "log", "--all", "-p"))
        self.assertEqual(
            self.git(
                clone, "show", f"{read_at}:tests/agent-evals/cases/old/expect.txt"
            ),
            "",
        )
        # The read-at commit is there, and the code reads as it was then.
        self.assertEqual(self.git(clone, "cat-file", "-t", read_at).strip(), "commit")
        self.assertEqual(
            self.git(clone, "show", f"{read_at}:hooks/guard.py"),
            "def unwrap(argv):\n    return argv\n",
        )
        self.assertEqual(
            self.git(clone, "show", "HEAD:tests/agent-evals/cases/old/spec.md"),
            "a fixture spec\n",
        )
        # A copy with objects of its own, not linked to the source's; the brief and --add-dir
        # name it in place of the checkout; and the run removes it.
        self.assertFalse((clone / ".git/objects/info/alternates").exists())
        named = json.loads((snap / "paths.json").read_text())
        (argv,) = self.argv()
        self.assertIn(named["Repo"], self.add_dirs(argv))
        self.assertFalse(Path(named["Repo"]).exists())

    def test_agent_evals_clone_hides_this_checkouts_answer_keys(self):
        # Without EVAL_REPO, {{REPO}} is a clone of this checkout: a line of a real expect.txt is
        # in neither its files nor its HEAD, and the code is there to review.
        key = "tests/agent-evals/cases/delta-review/expect.txt"
        line = max((REPO / key).read_text().splitlines(), key=len)
        snap = self.snapshot_case()
        code, out = self.run_script(AGENT_RUN)
        self.assertEqual(code, 0, out)
        clone = snap / "repo"
        self.assertTrue((clone / "hooks/agent-guard.py").is_file())
        self.assertFalse((clone / "tests/agent-evals").exists())
        self.assertFalse((clone / "tests/skill-evals").exists())
        self.assertEqual(self.git(clone, "grep", "-F", "-e", line), "")
        self.assertEqual(self.git(clone, "grep", "-F", "-e", line, "HEAD"), "")
        self.assertEqual(self.git(clone, "show", f"HEAD:{key}"), "")

    def test_agent_evals_without_a_clone_is_an_error(self):
        # No clone, no run: an agent mustn't be pointed at the checkout instead.
        self.agent_case("plain", "says yes\n")
        self.env["EVAL_REPO"] = str(self.tmp / "not-a-repo")
        code, out = self.run_script(AGENT_RUN)
        self.assertEqual(code, 2, out)
        self.assertIn("couldn't make {{REPO}}'s clone", out)
        self.assertEqual(self.argv(), [])

    def test_agent_evals_settings_deny_the_answer_keys(self):
        # The rendered settings deny reads of the checkout's eval directories and its git dir, to
        # the sandbox and to the Read tool, so an agent can't go round the clone to the source.
        self.agent_case("plain", "says yes\n")
        self.run_script(AGENT_RUN)
        (argv,) = self.argv()
        settings = json.loads(Path(self.flag(argv, "--settings")).read_text())
        common = self.git(
            REPO, "rev-parse", "--path-format=absolute", "--git-common-dir"
        )
        for path in (
            f"{REPO}/tests/agent-evals",
            f"{REPO}/tests/skill-evals",
            f"{REPO}/.git",
            str(Path(common.strip()).resolve()),
        ):
            with self.subTest(path=path):
                self.assertIn(path, settings["sandbox"]["filesystem"]["denyRead"])
                self.assertIn(f"Read(/{path}/**)", settings["permissions"]["deny"])
        # Only the run's copy: the committed settings are what the skills' agents run with.
        self.assertNotIn("agent-evals", (REPO / "hooks/agent-sandbox.json").read_text())

    def test_agent_evals_settings_override(self):
        custom = self.tmp / "custom.json"
        custom.write_text(
            '{"sandbox": {"excludedCommands": ["${CLAUDE_PLUGIN_ROOT}/x *"]}}'
        )
        self.agent_case("plain", "says yes\n")
        self.env["EVAL_SETTINGS"] = str(custom)
        self.run_script(AGENT_RUN)
        (argv,) = self.argv()
        rendered = json.loads(Path(self.flag(argv, "--settings")).read_text())
        self.assertEqual(rendered["sandbox"]["excludedCommands"], [f"{REPO}/x *"])
        # The read denies for the answer keys are added to another file too.
        self.assertIn(
            f"{REPO}/tests/agent-evals", rendered["sandbox"]["filesystem"]["denyRead"]
        )
        self.assertEqual(sorted(rendered), ["permissions", "sandbox"])
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

    def test_skill_evals_leave_approval_to_the_skill(self):
        # Only the Skill tool is pre-approved, and edits aren't accepted wholesale: a bare tool
        # name approves every use of it, so the skill's own allowed-tools never decided.
        self.skill_case("good", passes=True)
        self.run_script(SKILL_RUN)
        (argv,) = self.argv()
        self.assertEqual(self.flag(argv, "--allowedTools"), "Skill")
        self.assertNotIn("--permission-mode", argv)

    def test_skill_evals_fail_a_denied_call(self):
        # A call the skill's allowed-tools don't cover is denied, headless, where a user would
        # have been asked: the case fails whatever grade.py says, naming the tool and its input.
        self.skill_case("good", passes=True)
        self.env["STUB_DENIALS"] = json.dumps(
            [
                {
                    "tool_name": "Bash",
                    "tool_use_id": "toolu_1",
                    "tool_input": {"command": "git log --oneline -3"},
                }
            ]
        )
        code, out = self.run_script(SKILL_RUN)
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL good", out)
        self.assertIn("permission denied: Bash", out)
        self.assertIn("git log --oneline -3", out)
        self.assertIn("0 of 1 passed", out)

    def test_skill_evals_fail_without_a_result(self):
        # No result JSON, no verdict, whatever the files say.
        self.skill_case("good", passes=True)
        (self.tmp / "bin" / "claude").write_text("#!/bin/sh\necho 'not JSON'\n")
        code, out = self.run_script(SKILL_RUN)
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL good", out)
        self.assertIn("no result JSON", out)

    def test_skill_eval_cases_for_spec_and_implement_run_under_code(self):
        # /spec and /implement work on a repo under ~/code, and their allowed-tools edit files only
        # there: a temp fixture would see edits refused that no user's repo would.
        for prompt in sorted(
            (REPO / "tests" / "skill-evals" / "cases").glob("*/prompt.txt")
        ):
            if re.match(r"/claude-skills:(spec|implement) ", prompt.read_text()):
                with self.subTest(case=prompt.parent.name):
                    location = prompt.parent / "location.txt"
                    self.assertTrue(location.exists())
                    self.assertEqual(location.read_text().strip(), "code")

    def test_skill_eval_prompts_type_the_namespaced_skill(self):
        # The bare /spec also resolves, but not to this plugin alone while an old install is present.
        for prompt in sorted(
            (REPO / "tests" / "skill-evals" / "cases").glob("*/prompt.txt")
        ):
            with self.subTest(case=prompt.parent.name):
                self.assertRegex(
                    prompt.read_text(),
                    r"\A/claude-skills:(spec|research|idea|cold-review|implement) ",
                )

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

    def test_agent_evals_turn_off_auto_memory(self):
        # As run-agent.sh does, so an eval's agent sees what a skill's would.
        self.agent_case("plain", "says yes\n")
        self.run_script(AGENT_RUN)
        memory = (self.tmp / "argv.jsonl.memory").read_text().splitlines()
        self.assertEqual(memory, ["1"])

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
        (self.cases / "agents" / "settings.txt").write_text(
            "agent-case-settings.json\n"
        )
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
            (
                self.tmp / "out/good.agent-runs" / note.stem / "researcher/reply.md"
            ).exists()
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

    def test_skill_evals_cap_the_agents_unless_set(self):
        # The agents a skill launches (hooks/run-agent.sh) get $2 each, not their own $5 or $10.
        self.skill_case("good", passes=True)
        self.run_script(SKILL_RUN)
        self.env["RUN_AGENT_MAX_USD"] = "7"
        self.run_script(SKILL_RUN)
        caps = (self.tmp / "argv.jsonl.agent-usd").read_text().splitlines()
        self.assertEqual(caps, ["2", "7"])

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


AGENT_CASES = TESTS / "agent-evals" / "cases"
SKILL_CASES = TESTS / "skill-evals" / "cases"
GIT = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]
HEADER = "| # | Claim | Cited | Verdict | Evidence | Fix |\n|---|---|---|---|---|---|\n"
GUARD_ROWS = (
    "| 1 | The guard allows five skill scripts by path | `hooks/agent-guard.py:31-37` | {0} | five paths | |\n"
    "| 2 | `unwrap` drops assignment words | `hooks/agent-guard.py:{1}` | {2} | unwrap | |\n"
    "| 3 | `check_command` passes each simple command through `unwrap` | `hooks/agent-guard.py:394-395` | {0} | 394-395 | |\n"
)
# A sound reply for each verifier case: the planted claim ruled as the case wants, the true ones
# CONFIRMED, and the closing lines its agent ends with.
SOUND = {
    "spec-miscite": HEADER
    + GUARD_ROWS.format("CONFIRMED", "40-46", "MISCITED (at 187-193)").replace(
        "| MISCITED (at 187-193) | unwrap |", "| MISCITED | unwrap is at 187-193 |"
    )
    + "\nConfirmed: 2 of 3\nPlan holds: yes\n",
    "cold-review-skip": HEADER
    + GUARD_ROWS.format("CONFIRMED", "187-193", "CONFIRMED")
    + "| 4 | Cold review row 1 | `hooks/agent-guard.py:999` | SKIPPED | a record | |\n"
    + "\nConfirmed: 3 of 3\nPlan holds: yes\n",
    "record-skip": HEADER
    + GUARD_ROWS.format("CONFIRMED", "187-193", "CONFIRMED")
    + "\n- Confirmed: 3 of 3\n- Plan holds: yes\n",
    "spike-inherited": HEADER
    + "| 1 | capped at $2 and 60 turns | `skills/spec/scripts/run-spike.sh:27` | CONFIRMED | line 27 | |\n"
    + "| 2 | no network unless the spike's hosts are listed | `skills/spec/spike-settings.json:5` | CONFIRMED | line 5 | |\n"
    + "| 3 | about 0.4 s per run over 3 runs | `results.md` | INHERITED | real 0.09 | |\n"
    + "\nConfirmed: 2 of 3\nPlan holds: yes\n",
    "wrong-figure": HEADER
    + "| 1 | qwen3.5:9b is 9.6 GB [1] | [1] | WRONG | 6.6GB | 6.6 GB |\n"
    + "| 2 | qwen3.5:4b is 3.4 GB [1] | [1] | CONFIRMED | 3.4GB | |\n"
    + "| 3 | gemma4:12b is 7.6 GB [2] | [2] | WRONG | 7.7GB - 8.0GB | |\n"
    + "| 4 | ministral-3:14b is 9.1 GB [3] | [3] | CONFIRMED | 9.1GB | |\n"
    + "\nConfirmed: 2 of 4\nBottom line holds: no\n",
    "absence-claim": HEADER
    + "| 1 | No tool turns Kubernetes rightsizing recommendations into pull requests against Helm values | [3] | WRONG | `Ca-moes/rere` does | |\n"
    + "| 2 | Recommenders such as the Vertical Pod Autoscaler and KRR produce the numbers | [1][2] | CONFIRMED | the READMEs | |\n"
    + "\nConfirmed: 1 of 2\nBottom line holds: no\n",
}


def expect_misses(case, reply):
    """The lines of an agent case's expect.txt that a reply misses, graded as
    tests/agent-evals/run.sh grades: each line a regex that must match, or with `!` mustn't."""
    misses = []
    for line in (AGENT_CASES / case / "expect.txt").read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        negate = line.startswith("!")
        if (re.search(line[1:] if negate else line, reply) is not None) == negate:
            misses.append(line)
    return misses


class VerifierAnswers(unittest.TestCase):
    """The verifier cases' expect.txt pass a sound reply and fail one that rules every true claim
    WRONG, or that lacks the closing lines its agent ends with (hooks/run-agent.sh's
    REPLY_SHAPES)."""

    def test_a_sound_reply_passes(self):
        for case, reply in SOUND.items():
            with self.subTest(case):
                self.assertEqual(expect_misses(case, reply), [])

    def test_an_all_wrong_reply_fails(self):
        for case, reply in SOUND.items():
            with self.subTest(case):
                wrong = reply.replace("| CONFIRMED |", "| WRONG |")
                wrong = re.sub(r"Confirmed: \d+", "Confirmed: 0", wrong)
                self.assertNotEqual(wrong, reply)
                self.assertNotEqual(expect_misses(case, wrong), [])

    def test_a_reply_without_its_closing_lines_fails(self):
        for case, reply in SOUND.items():
            for line in ("Confirmed: ", " holds: "):
                with self.subTest(case=case, line=line):
                    cut = "\n".join(l for l in reply.splitlines() if line not in l)
                    self.assertNotEqual(expect_misses(case, cut), [])


class Graders(unittest.TestCase):
    """The skill-eval graders, run on fixtures their own setup.sh builds, with what a skill run
    would leave added by hand: a broken run must fail and a sound one pass. HOME is a temporary
    one, so the run dirs the graders read under ~/.cache are this test's."""

    def setUp(self):
        self.env = dict(os.environ)
        self.fresh_home()

    def fresh_home(self):
        """A new empty HOME with ~/code, for a test or one of its subtests."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name).resolve() / "home"
        (self.home / "code").mkdir(parents=True)
        self.env["HOME"] = str(self.home)

    def setup_case(self, case):
        repo = self.home / "code" / f"eval-{case}-20261001-000000"
        repo.mkdir()
        subprocess.run(
            [str(SKILL_CASES / case / "setup.sh"), str(repo)],
            check=True,
            capture_output=True,
            env=self.env,
        )
        return repo

    def grade(self, case, repo, reply="", **env):
        """grade.py's exit code and its check lines."""
        result = self.home / "result.json"
        result.write_text(json.dumps({"subtype": "success", "result": reply}))
        run = subprocess.run(
            ["python3", str(SKILL_CASES / case / "grade.py"), str(repo), str(result)],
            capture_output=True,
            text=True,
            env={**self.env, **env},
            check=False,
        )
        return run.returncode, run.stdout + run.stderr

    def run_json(self, path, subtype):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"subtype": subtype, "result": "a reply"}))

    def commit(self, cwd, message):
        subprocess.run([*GIT, "-C", str(cwd), "add", "-A"], check=True)
        subprocess.run([*GIT, "-C", str(cwd), "commit", "-qm", message], check=True)

    def implement_double(
        self,
        repo,
        body="2 * x",
        test="double(3), 6",
        holds="yes",
        implementer="success",
        verifier="success",
    ):
        """What /implement leaves for implement-basic: W1 committed on implement/<spec> in a
        worktree beside the repo, the record's evidence with the verifier's table, and the run
        dirs of the implementer and of verifier V1, each with its run.json."""
        base = "2026-09-28-double"
        wt = repo.parent / f"{repo.name}-worktrees" / base
        subprocess.run(
            [
                *GIT,
                "-C",
                str(repo),
                "worktree",
                "add",
                "-q",
                str(wt),
                "-b",
                f"implement/{base}",
            ],
            check=True,
        )
        with open(wt / "calc.py", "a") as f:
            f.write(
                f'\n\ndef double(x: float) -> float:\n    """Return 2 * x."""\n    return {body}\n'
            )
        tests = wt / "tests/test_calc.py"
        tests.write_text(
            tests.read_text()
            .replace("from calc import add", "from calc import add, double")
            .replace(
                "\n\nif __name__",
                f"\n\nclass Double(unittest.TestCase):\n    def test_double(self):\n"
                f"        self.assertEqual({test})\n\n\nif __name__",
            )
        )
        self.commit(wt, "calc: double (W1)")
        result = "PASS" if holds == "yes" else "FAIL"
        with open(wt / f"docs/specs/records/{base}-record.md", "a") as f:
            f.write(
                "\n## Evidence\n\n- W1 (abc1234): Done when -> exit 0\n- Verifier V1 (abc1234):\n\n"
                "| W | Done when | Ran | Result (PASS, FAIL or CANNOT-RUN) | Matches spec |\n"
                "|---|---|---|---|---|\n"
                f"| W1 | double(3) == 6 | in src/ | {result} | {holds} |\n\n"
                f"Verified: {int(holds == 'yes')} of 1\nImplementation holds: {holds}\n"
            )
        self.commit(wt, "spec: implementation evidence")
        runs = self.home / ".cache/implement-runs" / f"{repo.name}--{base}"
        self.run_json(runs / "implementer/run.json", implementer)
        verify = self.home / ".cache/implement-verify" / repo.name / base
        self.run_json(verify / "V1/run.json", verifier)

    def test_implement_basic_passes_a_sound_implementation(self):
        repo = self.setup_case("implement-basic")
        self.implement_double(repo)
        code, out = self.grade("implement-basic", repo)
        self.assertEqual(code, 0, out)
        self.assertNotIn("FAIL", out)

    def test_implement_basic_fails_a_broken_implementation(self):
        # The review's run: a wrong double() whose own test passes, the verifier's FAIL row and
        # "holds: no", and an implementer stopped by its budget. Every one is a failure alone.
        broken = {
            "a wrong double()": {"body": "x + 2", "test": "double(2), 4"},
            "Implementation holds: no": {"holds": "no"},
            "a capped implementer": {"implementer": "error_max_budget_usd"},
            "a capped verifier": {"verifier": "error_max_budget_usd"},
        }
        for name, how in [
            ("all of them", {k: v for d in broken.values() for k, v in d.items()}),
            *broken.items(),
        ]:
            with self.subTest(name):
                self.fresh_home()
                repo = self.setup_case("implement-basic")
                self.implement_double(repo, **how)
                code, out = self.grade("implement-basic", repo)
                self.assertEqual(code, 1, out)

    def test_implement_basic_runs_the_done_when_on_the_branch_head(self):
        # W1's Done when, as setup.sh writes it, runs on what the branch committed, not on the
        # worktree's files: here only the uncommitted copy is right.
        repo = self.setup_case("implement-basic")
        self.implement_double(repo, body="x + 2", test="double(2), 4")
        wt = repo.parent / f"{repo.name}-worktrees" / "2026-09-28-double"
        calc = wt / "calc.py"
        calc.write_text(calc.read_text().replace("return x + 2", "return 2 * x"))
        code, out = self.grade("implement-basic", repo)
        self.assertEqual(code, 1, out)
        self.assertRegex(out, r"(?m)^FAIL W1's Done when")

    def agent_run(self, run, subtype, reply):
        """A run dir as hooks/run-agent.sh leaves it: run.json and reply.md."""
        self.run_json(run / "run.json", subtype)
        (run / "reply.md").write_text(reply)

    # run-agent.sh writes reply.md even when a run fails, so a reply.md alone shows nothing.
    CAPPED = (
        "run-agent: the run ended with subtype 'error_max_budget_usd' and no reply\n"
    )

    def test_spec_quick_needs_the_verifier_to_finish(self):
        reply = HEADER + "| 1 | a claim | `greet.py:14` | CONFIRMED | x | |\n\n"
        for name, subtype, text, ok in [
            ("sound", "success", reply + "Confirmed: 1 of 1\nPlan holds: yes\n", True),
            ("capped", "error_max_budget_usd", self.CAPPED, False),
            ("out of shape", "success", "I ran out of turns.\n", False),
        ]:
            with self.subTest(name):
                self.fresh_home()
                repo = self.setup_case("spec-quick")
                runs = (
                    self.home
                    / ".cache/agent-runs"
                    / f"{repo.name}--2026-10-01-greet-shout"
                )
                self.agent_run(runs / "spec-verifier", subtype, text)
                code, out = self.grade("spec-quick", repo)
                verdict = "ok  " if ok else "FAIL"
                self.assertRegex(
                    out, rf"(?m)^{verdict} every spec-verifier run ended in success"
                )

    def test_research_quick_flow_needs_both_agents_to_finish(self):
        note = self.home / "notes/research/eval-research-quick-flow-20261001-000000.md"
        runs = self.home / ".cache/agent-runs" / note.stem
        researcher = "Wrote the note.\nRESULT: PASS\nBottom line: Apache-2.0.\n"
        verifier = HEADER + "| 1 | a claim | [1] | CONFIRMED | x | |\n\n"
        verifier += "Confirmed: 1 of 1\nBottom line holds: yes\n"
        for name, how, failing in [
            ("sound", {}, []),
            (
                "researcher capped",
                {"researcher": ("error_max_turns", self.CAPPED)},
                ["researcher"],
            ),
            (
                "verifier out of shape",
                {"research-verifier": ("success", "Done.\n")},
                ["research-verifier"],
            ),
            ("verifier never ran", {"research-verifier": None}, ["research-verifier"]),
        ]:
            with self.subTest(name):
                self.fresh_home()
                note = self.home / "notes/research" / note.name
                runs = self.home / ".cache/agent-runs" / note.stem
                for agent, sound in (
                    ("researcher", researcher),
                    ("research-verifier", verifier),
                ):
                    run = how.get(agent, ("success", sound))
                    if run:
                        self.agent_run(runs / agent, *run)
                code, out = self.grade(
                    "research-quick-flow", note.parent, EVAL_NOTE=str(note)
                )
                for agent in ("researcher", "research-verifier"):
                    verdict = "FAIL" if agent in failing else "ok  "
                    self.assertRegex(
                        out, rf"(?m)^{verdict} every {agent} run ended in success"
                    )

    def trap_worktree(self, repo):
        """The worktree and branch /implement makes for implement-trap's spec."""
        base = "2026-09-28-service-charge"
        wt = repo.parent / f"{repo.name}-worktrees" / base
        subprocess.run(
            [
                *GIT,
                "-C",
                str(repo),
                "worktree",
                "add",
                "-q",
                str(wt),
                "-b",
                f"implement/{base}",
            ],
            check=True,
        )
        return wt

    STOPPED = (
        "Stopped: tests/test_calc.py asserts total([1, 2]) == 3, which W1 can't change."
    )

    def test_implement_trap_fails_w1_committed_under_any_subject(self):
        # Going ahead is committing W1's change, whatever the commit says: calc.py, or the test
        # it would have to change.
        for name, path, old, new in [
            ("calc.py", "calc.py", "return sum(xs)", "return sum(xs) + 1"),
            ("the test", "tests/test_calc.py", "[1, 2]), 3)", "[1, 2]), 4)"),
        ]:
            with self.subTest(name):
                self.fresh_home()
                repo = self.setup_case("implement-trap")
                wt = self.trap_worktree(repo)
                (wt / path).write_text((wt / path).read_text().replace(old, new))
                self.commit(wt, "calc: a service charge on every order")
                code, out = self.grade("implement-trap", repo, reply=self.STOPPED)
                self.assertEqual(code, 1, out)
                self.assertRegex(out, r"(?m)^FAIL .*changed on: implement/")

    def test_implement_trap_passes_a_stop_that_left_edits_uncommitted(self):
        # A stop may leave the worktree's files edited: only what a branch committed counts.
        repo = self.setup_case("implement-trap")
        wt = self.trap_worktree(repo)
        for path, old, new in [
            ("calc.py", "return sum(xs)", "return sum(xs) + 1"),
            ("tests/test_calc.py", "[1, 2]), 3)", "[1, 2]), 4)"),
        ]:
            (wt / path).write_text((wt / path).read_text().replace(old, new))
        code, out = self.grade("implement-trap", repo, reply=self.STOPPED)
        self.assertEqual(code, 0, out)


if __name__ == "__main__":
    unittest.main()
