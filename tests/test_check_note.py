"""Tests for skills/research/scripts/check-note.py's Verification and word-limit checks.

Run with: python3 -m unittest discover -s ~/code/github.com/claude-skills/tests
"""

import importlib.util
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "skills" / "research" / "scripts" / "check-note.py"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "notes" / "verified-full.md"
HEADER = "Checked on 2026-09-15 by research-verifier: 1 of 2 claims confirmed."


def check(text, *flags):
    """(output, result line) from check-note.py on a note with this text."""
    with tempfile.TemporaryDirectory() as tmp:
        note = Path(tmp) / "note.md"
        note.write_text(text)
        run = subprocess.run(
            [sys.executable, str(CHECKER), *flags, str(note)],
            capture_output=True,
            text=True,
            check=False,  # exit 1 is a verdict
        )
    return run.stdout, run.stdout.strip().splitlines()[-1]


def words_above_sources(output):
    return int(re.search(r"(\d+) words above Sources", output).group(1))


def padded(text, extra_words):
    """The note with a Findings paragraph of extra_words words added."""
    pad = " ".join(["filler"] * extra_words)
    return text.replace("### Counter-evidence", f"{pad}\n\n### Counter-evidence", 1)


class Baseline(unittest.TestCase):
    def test_fixture_passes(self):
        out, result = check(FIXTURE.read_text())
        self.assertEqual(result, "RESULT: PASS", out)


class HeaderAgainstTable(unittest.TestCase):
    def test_mismatch_fails_a_final_note(self):
        text = FIXTURE.read_text().replace(HEADER, HEADER.replace("1 of 2", "2 of 3"))
        out, result = check(text)
        self.assertEqual(result, "RESULT: FAIL", out)
        self.assertRegex(out, r"FAIL: .*header says 2 of 3")

    def test_mismatch_warns_on_a_draft(self):
        text = FIXTURE.read_text().replace(HEADER, HEADER.replace("1 of 2", "2 of 3"))
        text = text.replace("status: final", "status: draft")
        out, result = check(text)
        self.assertEqual(result, "RESULT: PASS", out)
        self.assertRegex(out, r"WARN: .*header says 2 of 3")

    def test_header_without_counts_warns(self):
        text = FIXTURE.read_text().replace(
            HEADER, "Checked on 2026-09-15 by research-verifier."
        )
        out, _ = check(text)
        self.assertRegex(out, r"WARN: .*doesn't say 'N of M")


class SampleStated(unittest.TestCase):
    """The verifier checks a sample; the 'Checked on' line says how big a share."""

    def test_sample_unstated_warns(self):
        out, result = check(FIXTURE.read_text())
        self.assertEqual(result, "RESULT: PASS", out)
        self.assertIn("a sample of the note's 3 cited claims", out)

    def test_sample_stated_is_quiet(self):
        header = HEADER.replace("confirmed.", "confirmed, a sample of the note's 3 cited claims.")
        out, _ = check(FIXTURE.read_text().replace(HEADER, header))
        self.assertNotIn("cited in the note", out)

    def test_wrong_size_warns(self):
        header = HEADER.replace("confirmed.", "confirmed, a sample of the note's 9 cited claims.")
        out, _ = check(FIXTURE.read_text().replace(HEADER, header))
        self.assertIn("about 3 cited in the note", out)

    def test_counting(self):
        spec = importlib.util.spec_from_file_location("check_note", CHECKER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        prose = [
            "## Findings",
            "",
            "One is cited [1]. Two is not. Three is [2][3], and so on.",
            "- A bullet cites [4].",
            "- A bullet does not.",
            "",
            "| Repo | Stars |",
            "|---|---|",
            "| a/b | 10 [5] |",
            "| c/d | 20 |",
            "",
            "Code like `x[1]` isn't a citation.",
        ]
        self.assertEqual(module.cited_claims(prose), 4)


class LimitAfterVerification(unittest.TestCase):
    def setUp(self):
        self.base = FIXTURE.read_text()
        self.words = words_above_sources(check(self.base)[0])

    def over(self, fraction, text=None):
        extra = int(1500 * (1 + fraction)) - self.words
        return padded(text or self.base, extra)

    def test_five_percent_over_warns(self):
        out, result = check(self.over(0.05))
        self.assertEqual(result, "RESULT: PASS", out)
        self.assertRegex(out, r"WARN: .*over the 1500 limit after verification")

    def test_fifteen_percent_over_fails(self):
        out, result = check(self.over(0.15))
        self.assertEqual(result, "RESULT: FAIL", out)

    def test_unverified_note_over_fails(self):
        text = self.base.split("## Verification")[0].replace(
            "status: final", "status: draft"
        )
        out, result = check(self.over(0.05, text))
        self.assertEqual(result, "RESULT: FAIL", out)

    def test_headroom_budget_has_no_tolerance(self):
        extra = int(1300 * 1.05) - self.words
        out, result = check(padded(self.base, extra), "--headroom")
        self.assertEqual(result, "RESULT: FAIL", out)


class Placeholders(unittest.TestCase):
    def test_expression_in_inline_code_passes(self):
        text = padded(FIXTURE.read_text(), 0).replace(
            "### Counter-evidence",
            "Helm renders `{{ .Values.image }}` at install time.\n\n### Counter-evidence",
            1,
        )
        out, result = check(text)
        self.assertEqual(result, "RESULT: PASS", out)

    def test_placeholder_in_prose_fails(self):
        text = FIXTURE.read_text().replace(
            "### Counter-evidence", "Owned by {{owner}}.\n\n### Counter-evidence", 1
        )
        out, result = check(text)
        self.assertEqual(result, "RESULT: FAIL", out)
        self.assertIn("{{placeholder}}", out)


class PoolRowsAreNotStale(unittest.TestCase):
    """A Verification row may quote a Candidate pool line, which sits after Sources."""

    def test_row_quoting_pool_line(self):
        spec = importlib.util.spec_from_file_location("check_note", CHECKER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        body = [
            "## Bottom line",
            "",
            "Build the thing [1].",
            "",
            "## Sources",
            "",
            "1. [Thing](https://example.com): the thing.",
            "",
            "## Candidate pool",
            "",
            "- [tool] **Gizmo**: nobody has built a gizmo. Cut: too small.",
            "",
            "## Verification",
            "",
            "Checked on 2026-09-15 by research-verifier: 1 of 1 claims confirmed.",
            "",
            "| Claim | Cited | Verdict | Resolution |",
            "|---|---|---|---|",
            "| nobody has built a gizmo | [1] | CONFIRMED | |",
        ]
        prose, pool = body[:4], body[9:11]
        fails, warns = [], []
        module.check_verification(body, prose, "final", fails, warns, pool)
        self.assertFalse(
            [p for p in fails + warns if "no longer appears" in p], fails + warns
        )


if __name__ == "__main__":
    unittest.main()


class StaleRows(unittest.TestCase):
    """A Verification row vouches for a claim only while the note still says it, word for word."""

    def test_edited_number_is_stale(self):
        # "boxes of 12" still appears inside "boxes of 120"; the row must not vouch for it.
        text = FIXTURE.read_text().replace("boxes of 12 [2]", "boxes of 120 [2]")
        out, result = check(text)
        self.assertEqual(result, "RESULT: FAIL", out)
        self.assertIn("no longer appears in the note", out)

    def test_row_quoting_the_whole_sentence_matches(self):
        # The note reads "each [1]."; a row that quotes "each." is the same claim.
        text = FIXTURE.read_text().replace(
            "| Widgets weigh 3 kg each | [1]", "| Widgets weigh 3 kg each. | [1]"
        )
        out, result = check(text)
        self.assertEqual(result, "RESULT: PASS", out)

    def test_claim_split_across_paragraphs_is_stale(self):
        text = FIXTURE.read_text().replace(
            "Widgets weigh 3 kg each [1]. Gadgets ship in boxes of 12 [2].",
            "Widgets weigh 3 kg each [1]. Gadgets ship in boxes\n\nof 12 [2].",
        ).replace(" and gadgets ship in boxes of 12 [2]", "")
        out, result = check(text)
        self.assertEqual(result, "RESULT: FAIL", out)
        self.assertIn("no longer appears in the note", out)


class UnverifiedMarks(unittest.TestCase):
    """A row resolved as marked (unverified) needs the mark in the claim's own sentence."""

    def setUp(self):
        self.text = (
            FIXTURE.read_text()
            .replace("1 of 2 claims confirmed", "0 of 2 claims confirmed")
            .replace(
                "| Widgets weigh 3 kg each | [1] | CONFIRMED | |",
                "| Widgets weigh 3 kg each | [1] | UNREACHABLE | marked *(unverified)* |",
            )
        )

    def test_mark_in_the_claims_sentence_passes(self):
        text = self.text.replace("3 kg each [1]", "3 kg each [1] *(unverified)*")
        out, result = check(text)
        self.assertEqual(result, "RESULT: PASS", out)

    def test_mark_after_the_full_stop_passes(self):
        text = self.text.replace("3 kg each [1].", "3 kg each [1]. *(unverified)*").replace(
            "3 kg each [1],", "3 kg each [1] *(unverified)*,"
        )
        out, result = check(text)
        self.assertEqual(result, "RESULT: PASS", out)

    def test_mark_on_another_sentence_fails(self):
        text = self.text.replace("boxes of 12 [2].", "boxes of 12 [2] *(unverified)*.").replace(
            "3 kg each [1],", "3 kg each [1] *(unverified)*,"
        )
        out, result = check(text)
        self.assertEqual(result, "RESULT: FAIL", out)
        self.assertIn("isn't marked *(unverified)*", out)
