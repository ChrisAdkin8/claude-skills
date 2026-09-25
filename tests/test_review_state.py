"""Tests for skills/cold-review/scripts/review-state.py: which review round a document is due,
and the base its delta review diffs from.

Run with: python3 -m unittest discover -s ~/code/github.com/claude-skills/tests
"""

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


def state(doc):
    run = subprocess.run(
        [sys.executable, str(SCRIPT), str(doc)],
        capture_output=True,
        text=True,
        check=True,
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
            REVIEW + "\n### Delta review, 2026-09-22\n\nReviewed on 2026-09-22.\n",
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


if __name__ == "__main__":
    unittest.main()
