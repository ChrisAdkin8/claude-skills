"""Tests for skills/cold-review/scripts/review-state.py: which review round a document is due,
and the base its delta review diffs from.

Run with: python3 -m unittest discover -s ~/code/github.com/claude-skills/tests
"""

import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "cold-review" / "scripts" / "review-state.py"
DELTA_SETUP = (
    ROOT / "tests" / "skill-evals" / "cases" / "cold-review-delta" / "setup.sh"
)
DOC = "# Runbook\n\n## Steps\n\n1. Do it.\n\n## Rollback\n\nUndo it.\n"
REVIEW = (
    "# Record: Runbook\n\n## Cold review\n\n"
    "Reviewed on 2026-09-20 by cold-reviewer. Saved unchanged.\n\n| # | Kind |\n|---|---|\n"
)


SPEC = """---
title: "A spec"
status: reviewed # draft | reviewed | in-progress | done | superseded
read-at: 1111111
---

# A spec

## Goal

Make it work.

## Decision

- Use the launcher (`run.sh:10-12`).

## Background

Read at `1111111`. The launcher refuses early (`run.sh:10-12`, `:40`).

## Design

The gate calls `run.sh --check` (`gate.md:5`), as the launcher does at :40.

## Work items

### W1: check early

- **Change:** `run.sh --check`.
- **Done when:** a test shows `--check` exits 2.

## Open questions

None.
"""
DELTA = (
    "\n### Delta review, {date}\n\nReviewed on {date} by cold-reviewer: the changes logged as"
    " Not reviewed. Saved unchanged.\n\n| # | Kind |\n|---|---|\n"
)


def state(doc, home=None, *flags):
    run = subprocess.run(
        [sys.executable, str(SCRIPT), *flags, str(doc)],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "HOME": str(home)} if home else None,
    )
    return dict(
        line.split(": ", 1)
        for line in run.stdout.splitlines()
        if not line.startswith("logged")
    ), run.stdout


class ReviewState(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.doc = self.root / "docs" / "runbook.md"
        self.record = self.root / "docs" / "records" / "runbook-record.md"
        self.home = self.root.parent / f"{self.root.name}-home"
        self.home.mkdir()
        self.addCleanup(shutil.rmtree, self.home, True)

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.root), "-c", "user.name=t", "-c", "user.email=t@t", *args],
            capture_output=True, text=True, check=True,
        ).stdout.strip()  # fmt: skip

    def commit(self, message):
        self.git("add", ".")
        self.git("commit", "-qm", message)
        return self.git("rev-parse", "--short", "HEAD")

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def repo_with_review(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.write(self.doc, DOC)
        created = self.commit("doc")
        self.write(self.record, REVIEW)
        saved = self.commit("save review")
        return created, saved

    def test_no_review_is_full(self):
        self.write(self.doc, DOC)
        got, out = state(self.doc)
        self.assertEqual(got["state"], "full", out)
        self.assertEqual(got["repo"], "none")

    def test_unchanged_since_review(self):
        self.repo_with_review()
        got, out = state(self.doc)
        self.assertEqual(got["state"], "unchanged", out)

    def test_unlogged_change_names_its_heading(self):
        _, saved = self.repo_with_review()
        self.write(self.doc, DOC.replace("Undo it.", "Undo it, then restart."))
        got, out = state(self.doc)
        self.assertEqual(got["state"], "unlogged", out)
        # The review commit only added the record, so the base is that commit itself.
        self.assertEqual(got["base"], saved)
        self.assertEqual(got["headings"], "## Rollback")

    def test_logged_change_is_delta(self):
        self.repo_with_review()
        self.write(
            self.record,
            REVIEW
            + "\n## Changes since the review\n\n- **Not reviewed:** step 1, on 2026-09-21.\n",
        )
        got, out = state(self.doc)
        self.assertEqual(got["state"], "delta", out)
        self.assertEqual(got["not-reviewed"], "1")
        self.assertIn("logged: - **Not reviewed:** step 1", out)

    def test_delta_already_run_is_done(self):
        self.repo_with_review()
        self.write(
            self.record,
            REVIEW
            + "\n### Delta review, 2026-09-22\n\nReviewed on 2026-09-22 by cold-reviewer.\n",
        )
        got, out = state(self.doc)
        self.assertEqual(got["state"], "done", out)

    def test_review_never_committed_has_no_base(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.write(self.doc, DOC)
        self.commit("doc")
        self.write(self.record, REVIEW)
        got, out = state(self.doc)
        self.assertEqual(got["state"], "no-base", out)

    def test_older_document_keeps_its_review_inline(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.write(self.doc, DOC)
        self.commit("doc")
        self.write(self.doc, DOC + "\n" + REVIEW.split("\n", 2)[2])
        saved = self.commit("save review")
        got, out = state(self.doc)
        self.assertEqual(got["review"], "document", out)
        self.assertEqual(got["state"], "unchanged", out)
        self.assertEqual(got["base"], saved)

    def test_review_moved_into_a_record_diffs_from_before_the_save(self):
        # The skill eval's fixture: saved in the runbook, one fold logged, then moved into a
        # record, then an unlogged edit. The base is the parent of the save, not the move.
        subprocess.run([str(DELTA_SETUP), str(self.root)], check=True)
        hashes = dict(
            l.split("=", 1)
            for l in (self.root / ".git" / "eval-hashes").read_text().split()
        )
        got, out = state(self.doc)
        self.assertEqual(got["state"], "delta", out)
        self.assertEqual(got["base"], hashes["created"])
        self.assertEqual(got["headings"], "## Restore; ## Rollback")

    def test_edits_before_a_rename_still_found(self):
        _, saved = self.repo_with_review()
        self.write(self.doc, DOC + "\n## Verify\n\nCheck it.\n")
        self.commit("edit")
        new_doc = self.root / "docs" / "playbook.md"
        self.git("mv", str(self.doc), str(new_doc))
        self.git(
            "mv",
            str(self.record),
            str(self.root / "docs" / "records" / "playbook-record.md"),
        )
        self.commit("rename")
        got, out = state(new_doc)
        self.assertEqual(got["review-commit"], saved, out)
        self.assertEqual(got["state"], "unlogged", out)
        self.assertIn("## Verify", got["headings"])
        self.assertIn("docs/runbook.md docs/playbook.md", got["diff"])

    def test_headings_cover_every_changed_line(self):
        self.repo_with_review()
        self.write(self.doc, DOC + "\n## Verify\n\nCheck it.\n")
        got, out = state(self.doc)
        # The hunk starts on the blank line ending Rollback, and runs into the new section.
        self.assertEqual(got["headings"], "## Rollback; ## Verify", out)

    def test_code_block_heading_is_not_a_section(self):
        self.repo_with_review()
        self.write(self.doc, DOC + "\n```\n# a comment\nrun\n```\n")
        got, out = state(self.doc)
        self.assertEqual(got["headings"], "## Rollback", out)

    def test_cold_review_quoted_in_code_is_not_a_review(self):
        self.write(
            self.doc,
            DOC
            + "\n```markdown\n## Cold review\n\nReviewed on 2026-01-01 by cold-reviewer.\n```\n",
        )
        got, out = state(self.doc)
        self.assertEqual(got["review"], "none", out)
        self.assertEqual(got["state"], "full", out)

    def test_comment_in_code_does_not_hide_the_delta_review(self):
        self.repo_with_review()
        self.write(
            self.record,
            REVIEW
            + "\n```bash\n# re-run the checker\n```\n\n### Delta review, 2026-09-21\n"
            "\nReviewed on 2026-09-21 by cold-reviewer.\n"
            "\n## Changes since the review\n"
            "\n- Not reviewed: Rollback changed, on 2026-09-21.\n",
        )
        got, out = state(self.doc)
        self.assertEqual(got["delta-review"], "yes", out)
        self.assertEqual(got["state"], "done", out)

    def test_cold_review_heading_in_any_case(self):
        self.repo_with_review()
        self.write(
            self.record,
            REVIEW.replace("## Cold review", "## Cold Review")
            + "\n## Changes since the review\n"
            "\n- Not reviewed: Rollback changed, on 2026-09-21.\n",
        )
        got, out = state(self.doc)
        self.assertEqual(got["review"], "record", out)
        self.assertEqual(got["state"], "delta", out)

    def test_diff_line_is_quoted_and_runs_through_git_read(self):
        self.root = self.root / "sp ace"
        self.doc = self.root / "docs" / "my runbook.md"
        self.record = self.root / "docs" / "records" / "my runbook-record.md"
        self.repo_with_review()
        self.write(self.doc, DOC + "\nMore.\n")
        got, out = state(self.doc, self.home)
        # The script names git-read.py by where it is, quoted.
        hint = shlex.quote(str(ROOT / "hooks" / "git-read.py"))
        self.assertTrue(got["diff"].startswith(f"{hint} -C "), out)
        run = subprocess.run(
            ["bash", "-c", got["diff"]], capture_output=True, text=True, check=False
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("+More.", run.stdout)

    # The saved reply, and the lines /cold-review writes around it (the 2026-10-01 review parser).

    def test_legacy_deadlock_open_questions_count_once_a_record_exists(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.write(
            self.doc,
            "# Spec\n\n## Goal\n\nx\n\n## Open questions\n\n"
            "- Not reviewed: W1 changed, on 2026-09-21.\n\n" + REVIEW.split("\n", 2)[2],
        )
        self.write(self.record, "# Record: Spec\n\n## Verification\n\n- verified\n")
        self.commit("spec")
        got, out = state(self.doc)
        self.assertEqual(got["review"], "document", out)
        self.assertEqual(got["not-reviewed"], "1", out)
        self.assertEqual(got["state"], "delta", out)

    def test_delta_heading_without_its_reviewed_line_is_no_delta(self):
        self.repo_with_review()
        self.write(
            self.record,
            REVIEW + "\n### Delta review, 2026-09-22\n\n| # | Kind |\n|---|---|\n"
            "\n## Changes since the review\n\n- Not reviewed: Rollback, on 2026-09-21.\n",
        )
        got, out = state(self.doc)
        self.assertEqual(got["delta-review"], "no", out)
        self.assertEqual(got["state"], "delta", out)

    def test_findings_heading_in_the_reply_does_not_end_the_review(self):
        self.repo_with_review()
        self.write(
            self.record,
            REVIEW + "\n## Findings\n\nMore of the reply.\n"
            "\n### Delta review, 2026-09-22\n\nReviewed on 2026-09-22 by cold-reviewer.\n"
            "\n## Changes since the review\n\n- Not reviewed: Rollback, on 2026-09-21.\n",
        )
        got, out = state(self.doc)
        self.assertEqual(got["delta-review"], "yes", out)
        self.assertEqual(got["state"], "done", out)

    def test_not_reviewed_line_quoted_in_the_reply_is_not_counted(self):
        self.repo_with_review()
        self.write(
            self.record,
            REVIEW + "| 1 | says `- Not reviewed: x` |\n\n- Not reviewed: x\n",
        )
        self.commit("reply")
        got, out = state(self.doc)
        self.assertEqual(got["not-reviewed"], "0", out)
        self.assertEqual(got["state"], "unchanged", out)

    def test_reviewed_on_line_must_come_first(self):
        self.repo_with_review()
        self.write(
            self.record,
            "# Record: Runbook\n\n## Cold review\n\n| # | Kind |\n|---|---|\n"
            "| 1 | Reviewed on 2026-09-20 by cold-reviewer. |\n",
        )
        got, out = state(self.doc)
        self.assertEqual(got["review"], "none", out)
        self.assertEqual(got["state"], "full", out)

    def moved_without_record(self, *, commit):
        """The runbook `git mv`'d to playbook.md with its record left behind."""
        _, saved = self.repo_with_review()
        before, _ = state(self.doc)
        new_doc = self.root / "docs" / "playbook.md"
        self.git("mv", str(self.doc), str(new_doc))
        if commit:
            self.commit("move")
        got, out = state(new_doc)
        self.assertEqual(got["record-moved"], str(self.record.resolve()), out)
        self.assertEqual(got["record"], str(self.record.resolve()), out)
        self.assertEqual(got["review"], "record", out)
        self.assertEqual(got["review-commit"], before["review-commit"], out)
        self.assertEqual(got["review-commit"], saved, out)
        self.assertEqual(got["changed"], "no", out)
        self.assertEqual(got["state"], "unchanged", out)

    def test_document_moved_without_its_record_committed(self):
        self.moved_without_record(commit=True)

    def test_document_moved_without_its_record_staged(self):
        self.moved_without_record(commit=False)

    def test_unfilled_record_template_is_full_and_lists_placeholders(self):
        self.write(self.doc, DOC)
        template = ROOT / "skills" / "spec" / "record-template.md"
        self.write(self.record, template.read_text())
        got, out = state(self.doc)
        self.assertEqual(got["review"], "none", out)
        self.assertEqual(got["state"], "full", out)
        self.assertIn("placeholder: 1: {{spec title}}", out)
        self.assertIn("placeholder: 12: {{YYYY-MM-DD}}", out)

    def test_shallow_clone_cut_off_is_not_the_review_commit(self):
        self.repo_with_review()
        self.write(self.doc, DOC + "\n## Verify\n\nCheck it.\n")
        self.commit("edit")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        clone = Path(tmp.name) / "clone"
        subprocess.run(
            ["git", "clone", "-q", "--depth", "1", f"file://{self.root}", str(clone)],
            check=True,
        )
        got, out = state(clone / "docs" / "runbook.md")
        self.assertEqual(got["review-commit"], "none", out)
        self.assertEqual(got["state"], "no-base", out)

    # --plan, for /implement's gate: only the Decision, Design and Work items count, with their
    # citations' line numbers set aside.

    def spec_with_review(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.write(self.doc, SPEC)
        self.commit("spec")
        self.write(self.record, REVIEW)
        return self.commit("save review")

    def test_plan_sets_aside_status_read_at_and_re_cites(self):
        self.spec_with_review()
        self.write(
            self.doc,
            SPEC.replace("status: reviewed", "status: in-progress")
            .replace("1111111", "2222222")
            .replace("run.sh:10-12", "run.sh:11-14")
            .replace("gate.md:5", "gate.md:7")
            .replace(":40", ":42"),
        )
        self.commit("moved on and re-cited")
        got, out = state(self.doc, None, "--plan")
        self.assertEqual(got["state"], "unchanged", out)
        # Without --plan, every changed line counts, as /cold-review needs.
        got, out = state(self.doc)
        self.assertEqual(got["state"], "unlogged", out)

    def test_plan_counts_a_done_when_change(self):
        self.spec_with_review()
        self.write(self.doc, SPEC.replace("exits 2.", "exits 3."))
        self.commit("hand edit")
        got, out = state(self.doc, None, "--plan")
        self.assertEqual(got["state"], "unlogged", out)
        self.assertEqual(got["headings"], "### W1: check early", out)

    def test_plan_leaves_out_the_goal_and_background(self):
        self.spec_with_review()
        self.write(self.doc, SPEC.replace("Make it work.", "Make it work well."))
        got, out = state(self.doc, None, "--plan")
        self.assertEqual(got["state"], "unchanged", out)

    # After a delta review, a change since the commit that added its heading counts too.

    def test_an_unlogged_edit_after_a_delta_review_is_unlogged(self):
        self.repo_with_review()
        self.write(self.doc, DOC.replace("Do it.", "Do it twice."))
        self.write(
            self.record,
            REVIEW
            + DELTA.format(date="2026-09-22")
            + "\n## Changes since the review\n\n- Delta-reviewed on 2026-09-22: step 1.\n",
        )
        delta = self.commit("fold and delta review")
        self.write(
            self.doc, DOC.replace("Do it.", "Do it twice.").replace("Undo it.", "Undo.")
        )
        self.commit("hand edit")
        for flags in ((), ("--plan",)):
            with self.subTest(flags=flags):
                got, out = state(self.doc, None, *flags)
                self.assertEqual(got["delta-commit"], delta, out)
                self.assertEqual(got["base"], delta, out)
        got, out = state(self.doc)
        self.assertEqual(got["state"], "unlogged", out)
        self.assertEqual(got["headings"], "## Rollback", out)
        # Logged after the delta review, it's done: there is no third round.
        self.write(
            self.record,
            self.record.read_text()
            + "\n## Changes after the delta review\n\n- Not reviewed: Rollback, on 2026-09-23.\n",
        )
        got, out = state(self.doc)
        self.assertEqual(got["state"], "done", out)

    def test_a_plan_edit_after_a_delta_review_is_unlogged_under_plan(self):
        self.spec_with_review()
        self.write(self.record, REVIEW + DELTA.format(date="2026-09-22"))
        self.commit("delta review")
        self.write(self.doc, SPEC.replace("exits 2.", "exits 3."))
        self.commit("hand edit")
        got, out = state(self.doc, None, "--plan")
        self.assertEqual(got["state"], "unlogged", out)

    def test_a_delta_heading_in_another_case_is_found(self):
        self.spec_with_review()
        delta = DELTA.format(date="2026-09-22").replace("Delta review", "Delta Review")
        self.write(self.record, REVIEW + delta)
        commit = self.commit("delta review")
        self.write(self.doc, SPEC.replace("exits 2.", "exits 3."))
        self.commit("hand edit")
        got, out = state(self.doc, None, "--plan")
        self.assertEqual(got["delta-commit"], commit, out)
        self.assertEqual(got["state"], "unlogged", out)

    def test_plan_counts_a_port_change_and_sets_aside_other_citations(self):
        spec = SPEC.replace("(`gate.md:5`)", "(`gate.md:5`) on localhost:8080")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.write(self.doc, spec)
        self.commit("spec")
        self.write(self.record, REVIEW)
        self.commit("save review")
        self.write(self.doc, spec.replace("localhost:8080", "localhost:9090"))
        got, out = state(self.doc, None, "--plan")
        self.assertEqual(got["state"], "unlogged", out)
        self.write(
            self.doc,
            spec.replace("run.sh:10-12", "run.sh:11—14,20").replace(
                "gate.md:5", "gate.md:3,9"
            ),
        )
        got, out = state(self.doc, None, "--plan")
        self.assertEqual(got["state"], "unchanged", out)

    def test_full_and_delta_reviews_on_one_date_stay_apart(self):
        self.repo_with_review()  # reviewed on 2026-09-20
        self.write(self.doc, DOC.replace("Undo it.", "Undo it, then restart."))
        self.write(
            self.record,
            REVIEW
            + "\n## Changes since the review\n\n- Not reviewed: Rollback, on 2026-09-20.\n",
        )
        self.commit("fold")
        self.write(
            self.record,
            REVIEW
            + DELTA.format(date="2026-09-20")
            + "\n## Changes since the review\n\n- Delta-reviewed on 2026-09-20: Rollback.\n",
        )
        delta = self.commit("delta review")
        for flags in ((), ("--plan",)):
            with self.subTest(flags=flags):
                got, out = state(self.doc, None, *flags)
                self.assertEqual(got["delta-commit"], delta, out)
                self.assertEqual(got["state"], "done", out)

    def test_a_delta_review_saved_with_the_edits_it_reviewed_is_done(self):
        self.repo_with_review()
        self.write(self.doc, DOC.replace("Undo it.", "Undo it, then restart."))
        self.write(
            self.record,
            REVIEW
            + DELTA.format(date="2026-09-22")
            + "\n## Changes since the review\n\n- Delta-reviewed on 2026-09-22: Rollback.\n",
        )
        delta = self.commit("edits and their delta review")
        got, out = state(self.doc)
        # The base is the delta review's commit itself, never its parent.
        self.assertEqual(got["base"], delta, out)
        self.assertEqual(got["state"], "done", out)

    def test_a_delta_review_in_a_shallow_clone_cut_off_has_no_base(self):
        self.repo_with_review()
        self.write(self.record, REVIEW + DELTA.format(date="2026-09-22"))
        self.commit("delta review")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        clone = Path(tmp.name) / "clone"
        subprocess.run(
            ["git", "clone", "-q", "--depth", "1", f"file://{self.root}", str(clone)],
            check=True,
        )
        got, out = state(clone / "docs" / "runbook.md", None, "--plan")
        self.assertEqual(got["state"], "no-base", out)


if __name__ == "__main__":
    unittest.main()
