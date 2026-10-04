"""Tests for skills/research/scripts/mdcheck.py, the Markdown helpers check-note.py,
check-spec.py, build-index.py and review-state.py share: code blocks, headings, sections,
frontmatter and line counts.

Run with: python3 -m unittest discover -s ~/code/github.com/claude-skills/tests
"""

import importlib.util
import unittest
from pathlib import Path

PATH = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "research"
    / "scripts"
    / "mdcheck.py"
)
spec = importlib.util.spec_from_file_location("mdcheck", PATH)
assert spec and spec.loader
mdcheck = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mdcheck)


class CodeBlocks(unittest.TestCase):
    def test_fences_and_their_contents_are_code(self):
        lines = ["a", "```bash", "# not a heading", "```", "b", "~~~", "x", "~~~", "c"]
        self.assertEqual(mdcheck.strip_code(lines), ["a", "b", "c"])
        self.assertEqual(
            mdcheck.in_code(lines),
            [False, True, True, True, False, True, True, True, False],
        )

    def test_longer_fence_holds_a_shorter_one(self):
        lines = ["````", "```bash", "# inner", "```", "still code", "````", "after"]
        self.assertEqual(mdcheck.strip_code(lines), ["after"])

    def test_other_character_does_not_close(self):
        self.assertEqual(
            mdcheck.strip_code(["```", "~~~", "x", "```", "after"]), ["after"]
        )

    def test_closing_fence_has_nothing_after_it(self):
        self.assertEqual(
            mdcheck.strip_code(["```", "``` not a close", "```", "after"]), ["after"]
        )

    def test_inline_code_at_line_start_is_not_a_fence(self):
        lines = ["```x``` is inline code.", "## Next step", "Run it."]
        self.assertEqual(mdcheck.strip_code(lines), lines)

    def test_tilde_fence_may_carry_backticks(self):
        self.assertEqual(
            mdcheck.strip_code(["~~~ `info`", "x", "~~~", "after"]), ["after"]
        )

    def test_unclosed_fence_runs_to_the_end(self):
        self.assertEqual(mdcheck.strip_code(["a", "```", "b", "c"]), ["a"])


class Headings(unittest.TestCase):
    def test_heading_needs_a_space(self):
        for line in ("# A", "## B", "###### F", "##", "## "):
            with self.subTest(line=line):
                self.assertTrue(mdcheck.is_heading(line))
        for line in (
            "#2 on Hacker News",
            "####### seven",
            "#hashtag",
            " # indented",
            "text",
        ):
            with self.subTest(line=line):
                self.assertFalse(mdcheck.is_heading(line))

    def test_section_runs_past_hash_prose(self):
        lines = ["### Counter-evidence", "#2 on HN said so [1].", "## Options", "x"]
        self.assertEqual(
            mdcheck.section(lines, "### Counter-evidence"), ["#2 on HN said so [1]."]
        )

    def test_section_stops_at_same_or_higher_level(self):
        lines = ["## A", "a", "### A1", "a1", "## B", "b"]
        self.assertEqual(mdcheck.section(lines, "## A"), ["a", "### A1", "a1"])
        self.assertIsNone(mdcheck.section(lines, "## C"))

    def test_section_needs_the_whole_heading(self):
        """`## Cold review of any document` (README.md) isn't a saved cold review."""
        self.assertIsNone(
            mdcheck.section(["## Cold review of any document", "x"], "## Cold review")
        )
        for line in ("## Cold Review", "## Cold review:", "## Cold review, 2026-09-01"):
            with self.subTest(line=line):
                self.assertEqual(mdcheck.section([line, "x"], "## Cold review"), ["x"])

    def test_heading_is(self):
        self.assertTrue(mdcheck.heading_is("  ## Sources  ", "## Sources"))
        self.assertTrue(
            mdcheck.heading_is("### Delta review, 2026-09-27", "### Delta review")
        )
        self.assertFalse(mdcheck.heading_is("## Sources and notes", "## Sources"))
        self.assertFalse(mdcheck.heading_is("## Sourcesx", "## Sources"))


class Frontmatter(unittest.TestCase):
    def fields(self, *body):
        return mdcheck.frontmatter(["---", *body, "---", "text"])

    def test_quoted_value_keeps_its_hash(self):
        fields, start = self.fields(
            'title: "Fix for issue #42"', "other: 'a # b' # comment"
        )
        self.assertEqual(fields, {"title": "Fix for issue #42", "other": "a # b"})
        self.assertEqual(start, 4)

    def test_comment_stripped_from_plain_value(self):
        self.assertEqual(self.fields("status: draft # for now")[0], {"status": "draft"})

    def test_quotes_removed(self):
        self.assertEqual(self.fields('status: "reviewed"')[0], {"status": "reviewed"})

    def test_empty_value_and_block_list(self):
        fields = self.fields("related:", "  - ~/a.md", "- ~/b.md", "empty:")
        self.assertEqual(fields[0], {"related": "~/a.md, ~/b.md", "empty": ""})
        self.assertEqual(mdcheck.flow_list("[~/a.md, '~/b.md']"), ["~/a.md", "~/b.md"])

    def test_no_frontmatter(self):
        self.assertEqual(mdcheck.frontmatter(["# Title"]), ({}, 0))


class LineCount(unittest.TestCase):
    def test_counts_newlines_only(self):
        self.assertEqual(mdcheck.line_count("a\fb\x1cc d\ne"), 2)

    def test_final_line_with_or_without_newline(self):
        self.assertEqual(mdcheck.line_count(""), 0)
        self.assertEqual(mdcheck.line_count("a"), 1)
        self.assertEqual(mdcheck.line_count("a\n"), 1)
        self.assertEqual(mdcheck.line_count("a\n\n"), 2)
        self.assertEqual(mdcheck.line_count("a\r\nb\r\n"), 2)


class Citations(unittest.TestCase):
    def test_cite_matches_numbers_not_links(self):
        self.assertEqual(
            mdcheck.CITE.findall("x [1] y [2, 3] z [4-5] [6](url)"),
            ["1", "2, 3", "4-5"],
        )


class Loopholes(unittest.TestCase):
    """From the 2026-09-27 repo review: inputs that hid a document from the checks."""

    def test_unclosed_fence_is_reported(self):
        self.assertEqual(mdcheck.unclosed_fence(["a", "```bash", "b"]), 2)
        self.assertIsNone(mdcheck.unclosed_fence(["a", "```", "b", "```"]))

    def test_section_skips_code_and_ignores_case(self):
        lines = [
            "## Cold Review",
            "x",
            "```bash",
            "# comment",
            "```",
            "### Delta review",
            "## Next",
        ]
        self.assertEqual(mdcheck.section(lines, "## Cold review"), lines[1:6])
        self.assertIsNone(
            mdcheck.section(["```", "## Cold review", "```"], "## Cold review")
        )

    def test_rule_or_unclosed_block_is_not_frontmatter(self):
        self.assertEqual(
            mdcheck.frontmatter(["---", "# Title", "", "Prose.", "---", "more"]),
            ({}, 0),
        )
        self.assertEqual(mdcheck.frontmatter(["---", "title: x", "body"]), ({}, 0))
        fields, start = mdcheck.frontmatter(
            [
                "---",
                "title: x",
                "related:",
                "  - a",
                "# comment",
                "desc: >",
                "  folded",
                "---",
                "b",
            ]
        )
        self.assertEqual((fields["title"], fields["related"], start), ("x", "a", 8))

    def test_byte_order_mark_before_frontmatter(self):
        self.assertEqual(
            mdcheck.frontmatter(["\ufeff---", "title: x", "---"])[0], {"title": "x"}
        )


TABLE = ["| # | Kind |", "|---|---|", "| 1 | GAP |"]
REVIEW = ["## Cold review", "", "Reviewed on 2026-09-20 by cold-reviewer.", "", *TABLE]
DELTA = [
    "### Delta review, 2026-09-22",
    "",
    "Reviewed on 2026-09-22 by cold-reviewer: the changes logged as Not reviewed.",
    "",
    *TABLE,
]
CHANGES = [
    "## Changes since the review",
    "",
    "- Not reviewed: W1 changed, on 2026-09-21.",
]


def record(*sections):
    return ["# Record: x", "", "## Verification", "", "- verified"] + [
        line for part in sections for line in ["", *part]
    ]


class ReadReview(unittest.TestCase):
    """read_review(): the one reading of a saved cold review that review-state.py and
    check-spec.py share. It finds the review by the lines /cold-review writes around the
    reviewer's reply, never by text inside it."""

    def test_record_review_with_delta(self):
        rec = record(REVIEW, DELTA, CHANGES)
        got = mdcheck.read_review([], rec)
        self.assertEqual(got.where, "record")
        self.assertEqual((got.date, got.delta_date), ("2026-09-20", "2026-09-22"))
        self.assertEqual(rec[got.start], "## Cold review")
        self.assertEqual(rec[got.end], "## Changes since the review")
        self.assertEqual(
            got.not_reviewed,
            [("record ## Changes since the review", len(rec), CHANGES[2])],
        )
        self.assertEqual(got.placeholders, [])

    def test_delta_without_its_reviewed_line_is_no_delta(self):
        delta = [DELTA[0], "", *TABLE]
        got = mdcheck.read_review([], record(REVIEW, delta, CHANGES))
        self.assertEqual(got.where, "record")
        self.assertIsNone(got.delta_date)

    def test_findings_heading_in_the_reply_does_not_end_the_review(self):
        reply = [*REVIEW, "", "## Findings", "", "More of the reply."]
        rec = record(reply, DELTA, CHANGES)
        got = mdcheck.read_review([], rec)
        self.assertEqual(got.delta_date, "2026-09-22")
        self.assertEqual(rec[got.end], "## Changes since the review")

    def test_not_reviewed_line_in_the_reply_is_not_counted(self):
        reply = [*REVIEW, "", "- Not reviewed: quoted by the reviewer."]
        got = mdcheck.read_review([], record(reply))
        self.assertEqual(got.where, "record")
        self.assertEqual(got.not_reviewed, [])

    def test_guard_diff_review_is_neither_a_delta_nor_part_of_one(self):
        guard = [
            "### Guard diff review, 2026-09-30",
            "",
            "Reviewed on 2026-09-30 by cold-reviewer: the guard's diff.",
        ]
        got = mdcheck.read_review([], record(REVIEW, guard, CHANGES))
        self.assertIsNone(got.delta_date)
        late = [
            "### Delta review, 2026-09-22",
            "",
            *TABLE,
            "",
            *guard,
        ]  # the guard review's Reviewed on line isn't the delta's
        self.assertIsNone(mdcheck.read_review([], record(REVIEW, late)).delta_date)
        got = mdcheck.read_review([], record(REVIEW, DELTA, guard, CHANGES))
        self.assertEqual(got.delta_date, "2026-09-22")

    def test_reviewed_on_line_not_first_does_not_date_the_review(self):
        reply = ["## Cold review", "", *TABLE, "", "Reviewed on 2026-09-20 by someone."]
        got = mdcheck.read_review([], record(reply))
        self.assertIsNone(got.where)
        self.assertIsNone(got.date)

    def test_unfilled_record_template_is_no_review_and_lists_placeholders(self):
        template = (
            Path(__file__).resolve().parents[1]
            / "skills"
            / "spec"
            / "record-template.md"
        )
        got = mdcheck.read_review([], template.read_text().splitlines())
        self.assertIsNone(got.where)
        tokens = {token for _, token in got.placeholders}
        self.assertIn("{{YYYY-MM-DD}}", tokens)
        self.assertIn("{{spec title}}", tokens)
        self.assertEqual(got.placeholders[0], (1, "{{spec title}}"))

    def test_open_questions_lines_count_when_a_record_exists(self):
        doc = ["# Spec", "", "## Open questions", "", "- Not reviewed: W2 changed."]
        got = mdcheck.read_review(doc, record(["## Verification", "", "- ok"]))
        self.assertEqual(got.not_reviewed, [("document ## Open questions", 5, doc[4])])

    def test_changes_after_the_delta_and_spikes_are_counted(self):
        after = ["## Changes after the delta review", "", "- Not reviewed: later."]
        spikes = ["## Spikes", "", "- Not reviewed: from spike S1."]
        other = ["## Implementation", "", "- Not reviewed: not a fold."]
        got = mdcheck.read_review([], record(REVIEW, DELTA, after, spikes, other))
        self.assertEqual(
            [source for source, _, _ in got.not_reviewed],
            ["record ## Changes after the delta review", "record ## Spikes"],
        )

    def test_spec_template_heading_ends_an_inline_review(self):
        doc = ["# Spec", "", "## Goal", "", "x", "", *REVIEW, "", "## Findings", "",
               "## Open questions", "", "- None.", "", "## Effort"]  # fmt: skip
        got = mdcheck.read_review(doc, [])
        self.assertEqual(got.where, "document")
        self.assertEqual(doc[got.end], "## Open questions")
        self.assertEqual(got.misplaced, ["## Open questions", "## Effort"])
        self.assertEqual(mdcheck.read_review(doc[:13], []).misplaced, [])
        self.assertEqual(mdcheck.read_review(doc[:-1], []).end, len(doc) - 5)

    def test_inline_review_without_a_template_heading_runs_to_the_end(self):
        doc = ["# Spec", "", "## Goal", "", *REVIEW, "", "## Findings", "", "x"]
        got = mdcheck.read_review(doc, [])
        self.assertEqual(
            (got.where, got.end, got.misplaced), ("document", len(doc), [])
        )

    def test_quoted_placeholder_is_not_one(self):
        reply = [*REVIEW, "", "| 2 | WRONG | {{YYYY-MM-DD}} is left in |"]
        fold = ["## Changes since the review", "", "- Not reviewed: `{{N}}` filled in."]
        code = ["## Spikes", "", "```", "{{N}}", "```"]
        got = mdcheck.read_review([], record(reply, fold, code))
        self.assertEqual(got.placeholders, [])
        rec = record(reply, ["## Spikes", "", "- Question {{n}}: Route: spike."])
        self.assertEqual(
            mdcheck.read_review([], rec).placeholders, [(len(rec), "{{n}}")]
        )

    def test_record_tried_first(self):
        doc = ["# Spec", "", *REVIEW]
        self.assertEqual(mdcheck.read_review(doc, record(REVIEW)).where, "record")
        self.assertEqual(mdcheck.read_review(doc, record()).where, "document")
        self.assertIsNone(mdcheck.read_review(["# Spec"], None).where)


class RecordFor(unittest.TestCase):
    def test_finds_a_record_under_an_earlier_name(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            specs = Path(tmp)
            (specs / "records").mkdir()
            doc = specs / "new.md"
            self.assertIsNone(mdcheck.record_for(doc, [specs / "old.md"]))
            old_record = specs / "records" / "old-record.md"
            old_record.write_text("# Record\n")
            self.assertEqual(
                mdcheck.record_for(doc, [specs / "older.md", specs / "old.md"]),
                old_record,
            )
            new_record = specs / "records" / "new-record.md"
            new_record.write_text("# Record\n")
            self.assertEqual(mdcheck.record_for(doc, [specs / "old.md"]), new_record)


class CheckerGaps(unittest.TestCase):
    """From the 2026-10-04 review."""

    def test_stray_cold_review_heading_does_not_hide_the_review(self):
        record = [
            "# Record",
            "## Cold review",
            "",
            "To come.",
            "## Cold review",
            "",
            "Reviewed on 2026-10-01 by cold-reviewer.",
            "",
            "No findings.",
        ]
        got = mdcheck.read_review([], record)
        self.assertEqual((got.where, got.start, got.date), ("record", 4, "2026-10-01"))


if __name__ == "__main__":
    unittest.main()
