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


def state(doc, home=None):
    run = subprocess.run(
        [sys.executable, str(SCRIPT), str(doc)],
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

    def test_edits_before_a_rename_still_found(self):
        _, saved = self.repo_with_review()
        self.write(self.doc, DOC + "\n## Verify\n\nCheck it.\n")
        self.commit("edit")
        new_doc = self.root / "docs" / "playbook.md"
        self.git("mv", str(self.doc), str(new_doc))
        self.git("mv", str(self.record), str(self.root / "docs" / "records" / "playbook-record.md"))
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
        self.write(self.doc, DOC + "\n```markdown\n## Cold review\n\nReviewed on 2026-01-01 by cold-reviewer.\n```\n")
        got, out = state(self.doc)
        self.assertEqual(got["review"], "none", out)
        self.assertEqual(got["state"], "full", out)

    def test_comment_in_code_does_not_hide_the_delta_review(self):
        self.repo_with_review()
        self.write(
            self.record,
            REVIEW + "\n```bash\n# re-run the checker\n```\n\n### Delta review, 2026-09-21\n"
            "\n- Not reviewed: Rollback changed, on 2026-09-21.\n",
        )
        got, out = state(self.doc)
        self.assertEqual(got["delta-review"], "yes", out)
        self.assertEqual(got["state"], "done", out)

    def test_cold_review_heading_in_any_case(self):
        self.repo_with_review()
        self.write(self.record, REVIEW.replace("## Cold review", "## Cold Review")
                   + "\n- Not reviewed: Rollback changed, on 2026-09-21.\n")
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

    def test_shallow_clone_cut_off_is_not_the_review_commit(self):
        self.repo_with_review()
        self.write(self.doc, DOC + "\n## Verify\n\nCheck it.\n")
        self.commit("edit")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        clone = Path(tmp.name) / "clone"
        subprocess.run(
            ["git", "clone", "-q", "--depth", "1", f"file://{self.root}", str(clone)], check=True
        )
        got, out = state(clone / "docs" / "runbook.md")
        self.assertEqual(got["review-commit"], "none", out)
        self.assertEqual(got["state"], "no-base", out)

if __name__ == "__main__":
    unittest.main()
