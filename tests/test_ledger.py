"""Tests for skills/implement/scripts/ledger.py: the append-only ledger of what one spec's
implementer and verifier calls have cost, which run-implementer.sh reads its cap from.

Everything runs under a home of its own.
Run with: python3 -m unittest discover -s tests
"""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "skills" / "implement" / "scripts" / "ledger.py"
START = {"who": "implementer", "event": "start"}
END = {"who": "implementer", "event": "end"}


class Ledger(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name).resolve()
        self.env = {**os.environ, "HOME": str(self.home)}
        self.path = self.home / ".cache" / "implement-ledger" / "proj--spec.jsonl"

    def ledger(self, *args):
        run = subprocess.run(
            [str(SCRIPT), *args],
            capture_output=True,
            text=True,
            env=self.env,
            check=False,
        )
        return run.returncode, run.stdout.strip(), run.stderr

    def append(self, line):
        return self.ledger("append", "proj--spec", json.dumps(line))

    def lines(self):
        return [json.loads(line) for line in self.path.read_text().splitlines()]

    def test_is_executable(self):
        self.assertTrue(os.access(SCRIPT, os.X_OK))

    def test_path(self):
        self.assertEqual(self.ledger("path", "proj--spec"), (0, str(self.path), ""))
        for name in ("../x", "a/b", "", ".hidden", "a..b"):
            with self.subTest(name=name):
                self.assertEqual(self.ledger("path", name)[0], 2)

    def test_an_empty_ledger_has_spent_nothing(self):
        self.assertEqual(self.ledger("spent", "proj--spec"), (0, "0", ""))
        self.assertEqual(self.ledger("next-call", "proj--spec")[:2], (0, "1"))
        self.assertFalse(self.path.exists())

    def test_append_makes_a_private_dir_and_adds_at(self):
        self.assertEqual(self.append({**START, "call": 1, "budget": 20})[0], 0)
        self.assertEqual(oct(self.path.parent.stat().st_mode & 0o777), "0o700")
        (line,) = self.lines()
        self.assertIn("at", line)
        self.assertEqual(line["budget"], 20)

    def test_spent_sums_ends_or_budgets(self):
        for line in (
            {**START, "call": 1, "budget": 20},
            {**END, "call": 1, "usd": 2.5},
            {"who": "verifier V1", "usd": 3, "note": "finished"},
            {"who": "verifier V2", "usd": None, "note": "refused"},
            {**START, "call": 2, "budget": 17.5},
        ):
            self.assertEqual(self.append(line)[0], 0, line)
        self.assertEqual(self.ledger("spent", "proj--spec")[1], "20")
        self.assertEqual(self.ledger("next-call", "proj--spec")[1], "3")
        self.assertEqual(self.append({**END, "call": 2, "usd": 1.25})[0], 0)
        self.assertEqual(self.ledger("spent", "proj--spec")[1], "3.75")

    def test_append_refuses_a_line_out_of_order_or_out_of_shape(self):
        self.assertEqual(self.append({**START, "call": 1, "budget": 20})[0], 0)
        for line in (
            {**START, "call": 1, "budget": 20},  # a repeated call number
            {**START, "call": 3, "budget": 20},  # a skipped one
            {**END, "call": 2, "usd": 1},  # no start
            {**END, "call": 1, "usd": -1},
            {**END, "call": 1, "usd": True},
            {**END, "call": 1, "usd": "1"},
            {**END, "call": 1},
            {**END, "call": 1, "usd": 1, "extra": 1},
            {**START, "call": 2, "budget": 0},
            {"who": "verifier V1", "usd": -1, "note": ""},
            {"who": "verifier", "usd": 1, "note": ""},
            {"who": "someone else"},
            [1],
        ):
            with self.subTest(line=line):
                self.assertEqual(self.append(line)[0], 2)
        self.assertEqual(len(self.lines()), 1)
        self.assertEqual(self.append({**END, "call": 1, "usd": 1})[0], 0)
        self.assertEqual(self.append({**END, "call": 1, "usd": 1})[0], 2)
        code, _, err = self.ledger("append", "proj--spec", '{"usd": NaN}')
        self.assertEqual(code, 2, err)

    def test_a_bad_ledger_is_refused_naming_its_line(self):
        self.path.parent.mkdir(parents=True)
        for text in (
            "not json\n",
            '{"at": "x", "who": "implementer", "call": 1, "event": "start", "budget": Infinity}\n',
            '{"at": "x", "who": "implementer", "call": 1, "event": "start", "budget": 1}',
            '{"at": "x", "who": "implementer", "call": 2, "event": "end", "usd": 1}\n',
        ):
            with self.subTest(text=text):
                self.path.write_text(text)
                code, out, err = self.ledger("spent", "proj--spec")
                self.assertEqual(code, 2, out)
                self.assertIn(str(self.path), err)
                self.assertEqual(self.append({**START, "call": 1, "budget": 1})[0], 2)

    def test_a_symlinked_ledger_is_refused(self):
        self.path.parent.mkdir(parents=True)
        target = self.home / "elsewhere.jsonl"
        target.write_text("")
        self.path.symlink_to(target)
        self.assertEqual(self.ledger("spent", "proj--spec")[0], 2)
        self.assertEqual(self.append({**START, "call": 1, "budget": 1})[0], 2)
        self.assertEqual(target.read_text(), "")

    def test_bad_usage(self):
        for args in (
            (),
            ("spent",),
            ("append", "proj--spec"),
            ("remove", "proj--spec"),
        ):
            with self.subTest(args=args):
                self.assertEqual(self.ledger(*args)[0], 2)
        self.assertEqual(self.ledger("append", "proj--spec", "not json")[0], 2)


if __name__ == "__main__":
    unittest.main()
