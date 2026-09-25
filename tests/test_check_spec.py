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


HOUSE = """# Prompt: a house-format spec
{status}
## Role & Objective

Change nothing much.

## Deliverables

- **W1**: a thing.
"""
UNREVIEWED = RECORD + "\n## Changes since the review\n\n- Not reviewed: W1 changed, on 2026-09-24.\n"


class HouseStatus(unittest.TestCase):
    """A house-format spec has no frontmatter, so its status comes from its opening lines."""

    def test_no_status_warns_that_the_gate_cant_apply(self):
        out, result = check(HOUSE.format(status=""), record=UNREVIEWED)
        self.assertEqual(result, "RESULT: PASS", out)
        self.assertIn("states no status", out)
        self.assertIn("status ?", out)

    def test_status_line_is_read(self):
        for line in ("Status: in-progress", "**Status:** in-progress", "> Status: in-progress"):
            with self.subTest(line=line):
                out, result = check(HOUSE.format(status=f"\n{line}\n"), record=UNREVIEWED)
                self.assertEqual(result, "RESULT: FAIL", out)
                self.assertRegex(out, r"FAIL: 1 changes .*but the spec is in-progress")

    def test_shipped_banner_is_done(self):
        banner = "\n> ## SHIPPED - this is a RECORD, not a specification\n"
        out, result = check(HOUSE.format(status=banner), record=UNREVIEWED)
        self.assertEqual(result, "RESULT: PASS", out)
        self.assertIn("status done", out)
        self.assertNotIn("states no status", out)

    def test_status_list_item_is_read(self):
        out, result = check(HOUSE.format(status="\n- Status: reviewed\n"), record=UNREVIEWED)
        self.assertEqual(result, "RESULT: FAIL", out)
        self.assertRegex(out, r"FAIL: 1 changes .*but the spec is reviewed")

    def test_shipped_in_a_sentence_is_not_a_banner(self):
        status = "\nNothing has SHIPPED yet.\n\nStatus: reviewed\n"
        out, result = check(HOUSE.format(status=status), record=UNREVIEWED)
        self.assertEqual(result, "RESULT: FAIL", out)
        self.assertRegex(out, r"FAIL: 1 changes .*but the spec is reviewed")

    def test_quoted_frontmatter_status_is_read(self):
        text = '---\ntitle: x\nstatus: "reviewed"\n---\n' + HOUSE.format(status="")
        out, result = check(text, record=UNREVIEWED)
        self.assertEqual(result, "RESULT: FAIL", out)
        self.assertRegex(out, r"FAIL: 1 changes .*but the spec is reviewed")

    def test_unknown_house_status_warns(self):
        text = "---\ntitle: x\nstatus: approved\n---\n" + HOUSE.format(status="")
        out, result = check(text, record=UNREVIEWED)
        self.assertEqual(result, "RESULT: PASS", out)
        self.assertIn("status 'approved' isn't one this check knows", out)
        self.assertIn("states no status", out)

    def test_not_reviewed_variants_count(self):
        # Hand-written variants of the log line must still hold a reviewed spec back.
        for line in (
            "- **Not reviewed:** W1 changed.",
            "- **Not reviewed**: W1 changed.",
            "- not reviewed: W1 changed.",
            "* _Not reviewed:_ W1 changed.",
            "Not reviewed: W1 changed.",
        ):
            with self.subTest(line=line):
                record = RECORD + f"\n## Changes since the review\n\n{line}\n"
                out, result = check(HOUSE.format(status="\nStatus: reviewed\n"), record=record)
                self.assertEqual(result, "RESULT: FAIL", out)


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


def git_repo(root, files, message="init"):
    """Commit these files in a git repo at root (made if new); return the short commit."""
    root.mkdir(parents=True, exist_ok=True)
    if not (root / ".git").exists():
        subprocess.run(["git", "init", "-q", str(root)], check=True)
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@t",
         "commit", "-qm", message],
        check=True,
    )  # fmt: skip
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()  # fmt: skip


class Citations(unittest.TestCase):
    """path:line citations, checked against the cite repo as it was at read-at."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name) / "repo"
        self.read_at = git_repo(
            self.repo,
            {"src/app.py": "".join(f"line {n}\n" for n in range(1, 11)), "README.md": "hi\n"},
        )

    def check(self, background, read_at=None, extra=None, spec_text=None):
        text = spec_text or FIXTURE.read_text().replace(
            "read-at: none", f"read-at: {read_at or self.read_at}"
        ).replace("Nothing to cite, because read-at is none.", background)
        spec = self.repo / "docs" / "specs" / "spec.md"
        spec.parent.mkdir(parents=True, exist_ok=True)
        spec.write_text(text)
        run = subprocess.run(
            [sys.executable, str(CHECKER), str(spec), "--repo", str(self.repo), *(extra or [])],
            capture_output=True, text=True, check=False,
        )  # fmt: skip
        return run.stdout, run.stdout.strip().splitlines()[-1]

    def test_citation_in_range_passes(self):
        out, result = self.check("The app starts at src/app.py:3-5.")
        self.assertEqual(result, "RESULT: PASS", out)
        self.assertIn("1 citations to 1 files", out)

    def test_line_past_the_end_fails(self):
        out, result = self.check("See src/app.py:12.")
        self.assertEqual(result, "RESULT: FAIL", out)
        self.assertIn("src/app.py:12: the file had only 10 lines at read-at", out)

    def test_lines_added_after_read_at_fail(self):
        # The file grew after read-at; the spec describes it as it was.
        git_repo(self.repo, {"src/app.py": "".join(f"line {n}\n" for n in range(1, 21))}, "grow")
        out, result = self.check("See src/app.py:15.")
        self.assertEqual(result, "RESULT: FAIL", out)
        self.assertIn("had only 10 lines at read-at", out)

    def test_uncommitted_lines_warn(self):
        (self.repo / "src" / "app.py").write_text("".join(f"line {n}\n" for n in range(1, 21)))
        out, result = self.check("See src/app.py:15.")
        self.assertEqual(result, "RESULT: PASS", out)
        self.assertIn("uncommitted when the spec was read", out)

    def test_trailing_blank_lines_count(self):
        read_at = git_repo(self.repo, {"src/gap.py": "a\nb\nc\n\n\n"}, "gap")
        out, result = self.check("See src/gap.py:5.", read_at=read_at)
        self.assertEqual(result, "RESULT: PASS", out)

    def test_shorthand_uses_the_last_file(self):
        out, result = self.check("See src/app.py:2, then (:4) and (:11).")
        self.assertEqual(result, "RESULT: FAIL", out)
        self.assertIn("src/app.py:11: the file had only 10 lines", out)
        self.assertNotIn("src/app.py:4:", out)

    def test_shorthand_without_a_file_warns(self):
        out, _ = self.check("Then (:4).")
        self.assertIn("have no full citation earlier in their paragraph", out)

    def test_shorthand_does_not_cross_paragraphs(self):
        out, _ = self.check("See src/app.py:2.\n\nThen (:4).")
        self.assertIn("have no full citation earlier in their paragraph", out)

    def test_path_climbing_out_of_the_repo_fails(self):
        out, result = self.check("See ../other/app.py:2.")
        self.assertEqual(result, "RESULT: FAIL", out)
        self.assertIn("don't resolve", out)

    def test_missing_file_in_a_real_dir_fails(self):
        out, result = self.check("See src/gone.py:2.")
        self.assertEqual(result, "RESULT: FAIL", out)
        self.assertIn("src/gone.py:2: no such file", out)

    def test_bare_filename_warns(self):
        out, result = self.check("See app.py:2.")
        self.assertEqual(result, "RESULT: PASS", out)
        self.assertIn("give a bare filename", out)

    def test_citation_in_code_is_not_checked(self):
        for fence in ("```", "~~~"):
            with self.subTest(fence=fence):
                out, result = self.check(f"See src/app.py:1.\n\n{fence}\nsrc/gone.py:99\n{fence}")
                self.assertEqual(result, "RESULT: PASS", out)

    def test_host_port_is_not_a_citation(self):
        out, result = self.check("src/app.py:1 listens on svc/name:9090 and example.com:443.")
        self.assertEqual(result, "RESULT: PASS", out)
        self.assertIn("1 citations to 1 files", out)

    def test_read_at_line_is_used_with_frontmatter_lacking_read_at(self):
        # The file had 10 lines at read-at and 20 now; line 15 only exists now.
        git_repo(self.repo, {"src/app.py": "".join(f"line {n}\n" for n in range(1, 21))}, "grow")
        text = f"---\ntitle: x\n---\n# House spec\n\nRead at `{self.read_at}`. See src/app.py:15.\n"
        out, result = self.check("", spec_text=text)
        self.assertEqual(result, "RESULT: FAIL", out)
        self.assertIn("had only 10 lines at read-at", out)

    def test_cite_repo(self):
        other = self.repo.parent / "other"
        other_at = git_repo(other, {"lib/x.py": "one\ntwo\n"})
        text = FIXTURE.read_text().replace("read-at: none", f"read-at: {other_at}").replace(
            "cite-repo: none", f"cite-repo: {other}"
        ).replace("Nothing to cite, because read-at is none.", "See lib/x.py:2 and lib/x.py:3.")
        out, result = self.check("", spec_text=text)
        self.assertEqual(result, "RESULT: FAIL", out)
        self.assertIn("lib/x.py:3: the file had only 2 lines", out)
        self.assertIn("in other", out)


class WorkItems(unittest.TestCase):
    """Each work item needs a Done when with something in it."""

    def setUp(self):
        self.base = FIXTURE.read_text()

    def test_missing_done_when_fails(self):
        out, result = check(self.base.replace("- **Done when:** the tests pass.\n", ""))
        self.assertEqual(result, "RESULT: FAIL", out)
        self.assertIn("W1 has no 'Done when'", out)

    def test_empty_done_when_fails(self):
        out, result = check(self.base.replace("the tests pass.", ""))
        self.assertEqual(result, "RESULT: FAIL", out)
        self.assertIn("W1 has an empty 'Done when'", out)

    def test_done_when_as_nested_list_passes(self):
        text = self.base.replace("the tests pass.", "\n  - `make test` passes")
        out, result = check(text)
        self.assertEqual(result, "RESULT: PASS", out)

    def test_house_spec_with_acceptance_section_passes(self):
        text = HOUSE.format(status="\nStatus: draft\n").replace(
            "- **W1**: a thing.", "- **W1**: a thing.\n\n## Acceptance criteria\n\n- It runs."
        )
        out, result = check(text)
        self.assertEqual(result, "RESULT: PASS", out)
