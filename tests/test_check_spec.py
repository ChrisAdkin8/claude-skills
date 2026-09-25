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


def check(text, results=None, record=None):
    """(output, result line) from check-spec.py on a spec with this text, and with this text
    in its spike results file, `spikes/spec-results.md` beside it, and in its record,
    `records/spec-record.md`, if given."""
    with tempfile.TemporaryDirectory() as tmp:
        spec = Path(tmp) / "spec.md"
        spec.write_text(text)
        if results is not None:
            (Path(tmp) / "spikes").mkdir()
            (Path(tmp) / "spikes" / "spec-results.md").write_text(results)
        if record is not None:
            (Path(tmp) / "records").mkdir()
            (Path(tmp) / "records" / "spec-record.md").write_text(record)
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

    def test_long_draft_with_review_fails(self):
        # A saved review doesn't lift the limit: folds after the review are what grow a spec.
        out, result = check(with_review(self.long()))
        self.assertEqual(result, "RESULT: FAIL", out)
        self.assertRegex(
            out, r"FAIL: \d+ words; the limit is 4000.*keeping the saved cold review"
        )

    def test_long_spec_in_progress_fails(self):
        # Someone is working from it, so it's still the plan and the limit holds.
        text = self.long().replace("status: draft", "status: in-progress")
        out, result = check(with_review(text))
        self.assertEqual(result, "RESULT: FAIL", out)
        self.assertRegex(out, r"FAIL: \d+ words; the limit is 4000 while the spec is in-progress")

    def test_long_spec_done_warns(self):
        text = self.long().replace("status: draft", "status: done")
        out, result = check(with_review(text))
        self.assertEqual(result, "RESULT: PASS", out)
        self.assertRegex(out, r"WARN: \d+ words, over the 4000 limit; status done")

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


class Placeholders(unittest.TestCase):
    def setUp(self):
        self.base = FIXTURE.read_text()

    def with_background(self, extra):
        return self.base.replace(
            "Nothing to cite, because read-at is none.",
            f"Nothing to cite, because read-at is none. {extra}",
        )

    def test_expression_in_inline_code_passes(self):
        # Argo, Helm and Jinja write expressions as {{ ... }}; a spec quotes them in code.
        out, result = check(
            self.with_background("Argo passes `{{tasks.run-id.outputs.result}}` on.")
        )
        self.assertEqual(result, "RESULT: PASS", out)
        self.assertNotIn("placeholder", out)

    def test_expression_in_fenced_code_passes(self):
        text = self.with_background("Like this:\n\n```yaml\nvalue: {{ .Values.x }}\n```\n")
        out, result = check(text)
        self.assertEqual(result, "RESULT: PASS", out)

    def test_placeholder_in_prose_fails(self):
        out, result = check(self.with_background("Owned by {{owner}}."))
        self.assertEqual(result, "RESULT: FAIL", out)
        self.assertIn("{{placeholder}}", out)

    def test_placeholder_in_frontmatter_fails(self):
        out, result = check(self.base.replace("idea: none", "idea: {{idea note path}}"))
        self.assertEqual(result, "RESULT: FAIL", out)
        self.assertIn("{{placeholder}}", out)


class SpikeResultSecrets(unittest.TestCase):
    """Spike results are raw command output, committed beside the spec."""

    def setUp(self):
        self.base = FIXTURE.read_text()

    def test_clean_results_pass(self):
        out, result = check(self.base, results="# Spike results\n\nExit 0.\n")
        self.assertEqual(result, "RESULT: PASS", out)

    def test_token_in_results_fails(self):
        token = "gh" + "p_" + "A" * 36  # split, so this file doesn't look like a secret
        out, result = check(self.base, results=f"# Spike results\n\n{token}\n")
        self.assertEqual(result, "RESULT: FAIL", out)
        self.assertIn("spike results spec-results.md contain what looks like a GitHub token", out)

    def test_account_id_in_results_warns(self):
        out, result = check(self.base, results="account 123456789012 owns it\n")
        self.assertEqual(result, "RESULT: PASS", out)
        self.assertIn("spike results spec-results.md contain a 12-digit number", out)


DELTA = """
### Delta review, 2026-09-16

| # | Kind | Where | Finding | Affects | Evidence | What would settle it |
|---|---|---|---|---|---|---|
"""


class ChangesSinceReview(unittest.TestCase):
    """Changes folded in after the cold review are logged as `Not reviewed:` lines, and get
    one delta review."""

    def setUp(self):
        self.base = FIXTURE.read_text().replace(
            "- Nothing is open.",
            "- Nothing is open.\n- Not reviewed: W1 now does something, on 2026-09-16.",
        )

    def test_unreviewed_changes_warn(self):
        out, result = check(with_review(self.base))
        self.assertEqual(result, "RESULT: PASS", out)
        self.assertRegex(out, r"WARN: 1 changes since the cold review .*delta review")

    def test_delta_review_quiets_the_warning(self):
        out, result = check(with_review(self.base, REVIEW + DELTA))
        self.assertEqual(result, "RESULT: PASS", out)
        self.assertNotIn("WARN: 1 changes", out)
        self.assertIn("INFO: 1 changes marked 'Not reviewed:'", out)

    def test_no_warning_without_a_review(self):
        out, _ = check(self.base)
        self.assertNotIn("WARN: 1 changes", out)

    def test_reviewed_or_in_progress_fails_until_delta(self):
        # Status `reviewed` is the hand-off to implementation, so an unreviewed change blocks it.
        for status in ("reviewed", "in-progress"):
            with self.subTest(status=status):
                text = self.base.replace("status: draft", f"status: {status}", 1)
                out, result = check(with_review(text))
                self.assertEqual(result, "RESULT: FAIL", out)
                self.assertRegex(out, rf"FAIL: 1 changes .*no delta review, but the spec is {status}")
                out, result = check(with_review(text, REVIEW + DELTA))
                self.assertEqual(result, "RESULT: PASS", out)

    def test_done_only_warns(self):
        text = self.base.replace("status: draft", "status: done", 1)
        out, result = check(with_review(text))
        self.assertEqual(result, "RESULT: PASS", out)
        self.assertRegex(out, r"WARN: 1 changes since the cold review")


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

    def test_spike_lines_are_not_counted(self):
        # Step 7's folded lines are a record of the spike round, like the cold review: they
        # shouldn't push an author's spec over the word limit.
        base_words = words(check(self.base)[0])
        entry = (
            "   Route: spike\n"
            "   Changes: " + " ".join(["filler"] * 60) + "\n"
            "   Expect: " + " ".join(["filler"] * 60) + "\n"
            "   Box: $2, 60 turns; hosts: none\n"
            f"   Answered: {' '.join(['filler'] * 60)} (spike S1, `{EXISTING_RESULTS}`)\n"
        )
        out, result = check(with_spikes(self.base, entry))
        self.assertEqual(result, "RESULT: PASS", out)
        # Only the question line itself is counted, not the folded lines.
        self.assertLess(words(out) - base_words, 20, out)

    def test_long_spec_still_fails_without_spike_lines(self):
        pad = " ".join(["filler"] * 4200)
        text = self.base.replace(
            "Nothing to cite, because read-at is none.",
            f"Nothing to cite, because read-at is none. {pad}",
        )
        out, result = check(text)
        self.assertEqual(result, "RESULT: FAIL", out)
        self.assertRegex(out, r"FAIL: \d+ words; the limit is 4000")

    def test_one_answer_line_per_question_does_not_warn(self):
        entry = f"   Route: spike\n   Answered: it runs (spike S1, `{EXISTING_RESULTS}`)\n"
        text = with_spikes(self.base, entry).replace(
            "## Open questions", "2. Is it fast? Experiment: time it.\n   Open: needs docker\n\n## Open questions", 1
        )
        out, result = check(text)
        self.assertEqual(result, "RESULT: PASS", out)
        self.assertNotIn("more than one", out)


RECORD = """# Record: a spec

""" + REVIEW


class Record(unittest.TestCase):
    """Review history lives in records/<basename>-record.md beside the spec."""

    def setUp(self):
        self.base = FIXTURE.read_text()

    def test_spec_with_record_passes_quietly(self):
        out, result = check(self.base, record=RECORD)
        self.assertEqual(result, "RESULT: PASS", out)
        self.assertNotIn("review history kept in the spec", out)

    def test_changes_logged_in_record_warn_until_delta(self):
        record = RECORD + "\n## Changes since the review\n\n- Not reviewed: W1 changed, on 2026-09-24.\n"
        out, _ = check(self.base, record=record)
        self.assertRegex(out, r"WARN: 1 changes since the cold review .*delta review")
        out, _ = check(self.base, record=RECORD + DELTA + record[len(RECORD):])
        self.assertNotIn("WARN: 1 changes", out)
        self.assertIn("INFO: 1 changes marked 'Not reviewed:' in spec-record.md", out)

    def test_history_in_spec_warns(self):
        out, result = check(with_review(self.base))
        self.assertEqual(result, "RESULT: PASS", out)
        self.assertIn("review history kept in the spec: the '## Cold review' section", out)

    def test_spike_routing_in_spec_warns(self):
        entry = f"   Route: spike\n   Box: $2\n   Answered: it runs (spike S1, `{EXISTING_RESULTS}`)\n"
        out, _ = check(with_spikes(self.base, entry))
        self.assertIn("2 Route/Changes/Expect/Box lines under spike questions", out)

    def test_history_in_done_spec_is_left_alone(self):
        out, _ = check(with_review(self.base.replace("status: draft", "status: done")))
        self.assertNotIn("review history kept in the spec", out)

    def test_implemented_but_draft_warns(self):
        record = RECORD + "\n## Implementation\n\n- 2026-09-24, W1 (abc1234): it differed.\n"
        out, result = check(self.base, record=record)
        self.assertEqual(result, "RESULT: PASS", out)
        self.assertIn("1 implementation notes but the spec is still draft", out)

    def test_secrets_checked_in_record(self):
        token = "gh" + "p_" + "A" * 36
        out, result = check(self.base, record=RECORD + f"\nleaked {token}\n")
        self.assertEqual(result, "RESULT: FAIL", out)
        self.assertIn("its record spec-record.md contains what looks like a GitHub token", out)


class Numbering(unittest.TestCase):
    def test_later_part_keeps_its_numbers(self):
        base = FIXTURE.read_text()
        self.assertIn("### W1", base)
        out, result = check(base.replace("### W1", "### W4"))
        self.assertEqual(result, "RESULT: PASS", out)
        self.assertNotIn("numbered", out)

    def test_gap_warns(self):
        base = FIXTURE.read_text()
        text = base.replace("## Spike questions", "### W3: another\n\n- **Change:** x\n- **Files:** y\n- **Done when:** `true` exits 0\n\n## Spike questions", 1)
        out, _ = check(text)
        self.assertIn("work items are numbered [1, 3]", out)


if __name__ == "__main__":
    unittest.main()
