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


if __name__ == "__main__":
    unittest.main()
