"""Tests for tests/agent-evals/run.sh and tests/skill-evals/run.sh: they exit 1 when a case fails,
0 only when every case passes, and 2 on a case that doesn't exist.

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
AGENT_RUN = TESTS / "agent-evals" / "run.sh"
SKILL_RUN = TESTS / "skill-evals" / "run.sh"
STUB = """#!/usr/bin/env python3
import json
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
        }

    def run_script(self, script, *cases):
        run = subprocess.run(
            [str(script), *cases],
            capture_output=True,
            text=True,
            env=self.env,
            check=False,
        )
        return run.returncode, run.stdout + run.stderr

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
        self.skill_case("good", passes=True)
        self.run_script(SKILL_RUN)
        result = json.loads((self.tmp / "out" / "good.json").read_text())
        self.assertEqual(result["result"], "the reply says yes")


if __name__ == "__main__":
    unittest.main()
