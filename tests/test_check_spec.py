"""Tests for skills/spec/scripts/check-spec.py's handling of a saved cold review and spike results.

Run with: python3 -m unittest discover -s ~/code/github.com/claude-skills/tests
"""

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "skills" / "spec" / "scripts" / "check-spec.py"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "specs" / "draft-spec.md"
# A reviewer's table can cite lines that don't exist and notes that were never written; the
# spec can't fix either, since the review is saved unchanged.
REVIEW = """## Cold review

Reviewed on 2026-09-15 by spec-reviewer.

| # | Kind | Where | Finding | Affects | Evidence | What would settle it |
|---|---|---|---|---|---|---|
| 1 | COST | W1 | Nothing changes | neither: a fixture | hooks/agent-guard.py:999 | See ~/notes/research/does-not-exist.md |
"""


def check(text):
    """(output, result line) from check-spec.py on a spec with this text."""
    with tempfile.TemporaryDirectory() as tmp:
        spec = Path(tmp) / "spec.md"
        spec.write_text(text)
        run = subprocess.run(
            [sys.executable, str(CHECKER), str(spec), "--repo", str(ROOT)],
            capture_output=True,
            text=True,
            check=False,  # exit 1 is a verdict
        )
    return run.stdout, run.stdout.strip().splitlines()[-1]


def words(output):
    return int(re.search(r"(\d+) words, status", output).group(1))


def with_review(text, review=REVIEW):
    return text.rstrip("\n") + "\n\n" + review


class ColdReview(unittest.TestCase):
    def setUp(self):
        self.base = FIXTURE.read_text()
        self.base_words = words(check(self.base)[0])

    def long(self, total=4200):
        pad = " ".join(["filler"] * (total - self.base_words))
        return self.base.replace(
            "Nothing to cite, because read-at is none.",
            f"Nothing to cite, because read-at is none. {pad}",
        )

    def test_fixture_passes(self):
        out, result = check(self.base)
        self.assertEqual(result, "RESULT: PASS", out)

    def test_long_draft_without_review_fails(self):
        out, result = check(self.long())
        self.assertEqual(result, "RESULT: FAIL", out)
        self.assertRegex(out, r"FAIL: \d+ words; the limit is 4000")

    def test_long_draft_with_review_warns(self):
        out, result = check(with_review(self.long()))
        self.assertEqual(result, "RESULT: PASS", out)
        self.assertRegex(
            out, r"WARN: \d+ words, over the 4000 limit; a cold review is saved"
        )

    def test_review_is_not_checked(self):
        # Its bad citation and missing note would FAIL anywhere else in the spec.
        out, result = check(with_review(self.base))
        self.assertEqual(result, "RESULT: PASS", out)
        self.assertNotIn("999", out)
        self.assertNotIn("does-not-exist", out)

    def test_review_words_are_not_counted(self):
        big = REVIEW + "\n" + " ".join(["finding"] * 3500) + "\n"
        out, _ = check(with_review(self.base, big))
        self.assertEqual(words(out), self.base_words, out)

    def test_review_must_be_last(self):
        text = self.base.replace("## Open questions", REVIEW + "\n## Open questions")
        out, _ = check(text)
        self.assertRegex(out, r"WARN: '## Cold review' isn't the spec's last section")

    def test_secrets_still_checked_in_review(self):
        # A split-up token, so this file doesn't itself look like a secret.
        token = "gh" + "p_" + "A" * 36
        out, result = check(with_review(self.base, REVIEW + f"\nleaked {token}\n"))
        self.assertEqual(result, "RESULT: FAIL", out)
        self.assertIn("GitHub token", out)


EXISTING_RESULTS = "docs/specs/spikes/2026-09-17-spec-spike-phase-results.md"


def with_spikes(text, entry):
    """The fixture with its Spike questions section replaced by one question and these lines."""
    question = "1. Does the checker run? Experiment: run it once.\n" + entry
    return text.replace("## Spike questions\n\nNone.", "## Spike questions\n\n" + question)


class SpikeResults(unittest.TestCase):
    def setUp(self):
        self.base = FIXTURE.read_text()
        self.assertIn("## Spike questions\n\nNone.", self.base)

    def test_missing_results_file_fails(self):
        for prefix in ("Answered:", "Partly answered:", "Open:"):
            with self.subTest(prefix=prefix):
                entry = f"   {prefix} it runs (spike S1, `docs/specs/spikes/nope-results.md`)\n"
                out, result = check(with_spikes(self.base, entry))
                self.assertEqual(result, "RESULT: FAIL", out)
                self.assertRegex(out, r"FAIL: .*spikes/nope-results.md")

    def test_existing_results_file_passes(self):
        entry = f"   Answered: it runs (spike S1, `{EXISTING_RESULTS}`)\n"
        self.assertTrue((ROOT / EXISTING_RESULTS).is_file())
        out, result = check(with_spikes(self.base, entry))
        self.assertEqual(result, "RESULT: PASS", out)

    def test_results_line_in_review_not_checked(self):
        review = REVIEW + "\n   Answered: it runs (spike S1, `docs/specs/spikes/nope-results.md`)\n"
        out, result = check(with_review(self.base, review))
        self.assertEqual(result, "RESULT: PASS", out)
        self.assertNotIn("nope-results", out)

    def test_results_path_on_other_lines_not_checked(self):
        # A spec may name a results path in prose, e.g. its Design, before any spike has run.
        text = self.base.replace(
            "Nothing to cite, because read-at is none.",
            "Nothing to cite, because read-at is none. Results go to "
            "`docs/specs/spikes/nope-results.md`.",
        )
        out, result = check(text)
        self.assertEqual(result, "RESULT: PASS", out)
        self.assertNotIn("nope-results", out)

    def test_two_answer_lines_warn(self):
        entry = (
            f"   Answered: it runs (spike S1, `{EXISTING_RESULTS}`)\n"
            "   Open: needs docker\n"
        )
        out, result = check(with_spikes(self.base, entry))
        self.assertEqual(result, "RESULT: PASS", out)
        self.assertRegex(out, r"WARN: spike question 1 has more than one")

    def test_one_answer_line_per_question_does_not_warn(self):
        entry = f"   Route: spike\n   Answered: it runs (spike S1, `{EXISTING_RESULTS}`)\n"
        text = with_spikes(self.base, entry).replace(
            "## Open questions", "2. Is it fast? Experiment: time it.\n   Open: needs docker\n\n## Open questions", 1
        )
        out, result = check(text)
        self.assertEqual(result, "RESULT: PASS", out)
        self.assertNotIn("more than one", out)


if __name__ == "__main__":
    unittest.main()
