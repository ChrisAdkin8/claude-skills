"""Tests for skills/research/scripts/build-index.py, the generated notes index.

Run with: python3 -m unittest discover -s ~/code/github.com/claude-skills/tests
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "skills" / "research" / "scripts" / "build-index.py"


def note(title, status, topic=None, related=()):
    lines = ["---", f"title: {title}", f"status: {status}"]
    if topic:
        lines.append(f"topic: {topic}")
    lines.append(f"related: [{', '.join(related)}]")
    return "\n".join(lines + ["---", "", f"# {title}", ""])


class BuildIndex(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        for kind in ("research", "ideas", "decisions"):
            (self.root / kind).mkdir()

    def write(self, rel, text):
        (self.root / rel).write_text(text)

    def build(self):
        """build-index.py's printed line, and the index it wrote."""
        run = subprocess.run(
            [sys.executable, str(BUILDER), str(self.root)],
            capture_output=True,
            text=True,
            check=True,
        )
        return run.stdout, (self.root / "index.md").read_text()

    def lines(self):
        return self.build()[1].splitlines()

    def test_two_level_topic_gives_area_and_sub_area_headings(self):
        self.write(
            "research/a.md", note("Note A", "final", "claude-code/research-skill")
        )
        lines = self.lines()
        at = lines.index("## claude-code")
        self.assertLess(at, lines.index("### research-skill"))
        self.assertIn("- [Note A](research/a.md) · final", lines)

    def test_one_level_topic_goes_straight_under_the_area(self):
        self.write("research/a.md", note("Note A", "final", "kubernetes"))
        self.write("research/b.md", note("Note B", "draft", "kubernetes/tools"))
        lines = self.lines()
        self.assertEqual(
            lines[lines.index("## kubernetes") :][:5],
            ["## kubernetes", "", "- [Note A](research/a.md) · final", "", "### tools"],
        )

    def test_idea_is_indented_under_its_research_note(self):
        self.write("research/a.md", note("Note A", "final", "kubernetes"))
        self.write(
            "ideas/i.md",
            note(
                "Idea I",
                "parked",
                related=["~/code/github.com/x", "~/notes/research/a.md"],
            ),
        )
        lines = self.lines()
        at = lines.index("- [Note A](research/a.md) · final")
        self.assertEqual(lines[at + 1], "  - [Idea I](ideas/i.md) · parked")

    def test_related_resolves_against_the_given_folder(self):
        # A research note of this name exists in the temporary folder, and almost certainly
        # not in the real ~/notes; the idea must still find it.
        self.write("research/2099-01-01-only-here.md", note("Only here", "final", "a"))
        self.write(
            "ideas/i.md",
            note(
                "Idea I", "seed", related=["~/notes/research/2099-01-01-only-here.md"]
            ),
        )
        lines = self.lines()
        at = lines.index("- [Only here](research/2099-01-01-only-here.md) · final")
        self.assertEqual(lines[at + 1], "  - [Idea I](ideas/i.md) · seed")

    def test_no_topic_and_no_research_parent_are_unfiled(self):
        self.write("research/a.md", note("Note A", "final"))
        self.write("research/b.md", note("Note B", "final", "a/b/c"))
        self.write(
            "decisions/d.md", note("Decision D", "accepted", related=["~/notes/x.md"])
        )
        out, text = self.build()
        unfiled = text.split("## Unfiled\n", 1)[1]
        for line in (
            "- [Note A](research/a.md)",
            "- [Note B](research/b.md)",
            "- [Decision D](decisions/d.md)",
        ):
            self.assertIn(line, unfiled)
        self.assertIn("0 topics, 3 notes, 3 unfiled", out)

    def test_ideas_of_an_unfiled_note_are_kept(self):
        self.write("research/a.md", note("Note A", "final"))
        self.write(
            "ideas/i.md", note("Idea I", "seed", related=["~/notes/research/a.md"])
        )
        unfiled = self.build()[1].split("## Unfiled\n", 1)[1]
        self.assertIn(
            "- [Note A](research/a.md) · final\n  - [Idea I](ideas/i.md) · seed",
            unfiled,
        )

    def test_counts_one_topic_per_area_and_sub_area_in_use(self):
        self.write("research/a.md", note("Note A", "final", "a/x"))
        self.write("research/b.md", note("Note B", "final", "b"))
        self.write("ideas/i.md", note("Idea I", "seed", related=["~/notes/research/b.md"]))
        self.assertIn("2 topics, 3 notes, 0 unfiled", self.build()[0])

    def test_awkward_file_names_keep_their_links(self):
        self.write("research/a.md", note("Note A", "final", "a"))
        self.write("ideas/my idea (v2).md", note("Idea", "seed", related=["~/notes/research/a.md"]))
        self.write("ideas/odd<name>.md", note("Odd", "seed", related=["~/notes/research/a.md"]))
        text = self.build()[1]
        self.assertIn("  - [Idea](<ideas/my idea (v2).md>) · seed", text)
        self.assertIn("  - [Odd](ideas/odd%3Cname%3E.md) · seed", text)
        self.assertIn("- [Note A](research/a.md) · final", text)  # plain names are unchanged

    def test_dotfile_is_left_out(self):
        self.write("research/a.md", note("Note A", "final", "a"))
        self.write("research/.eval-case-1.md", note("Eval note", "draft", "a"))
        self.assertNotIn("Eval note", self.build()[1])

    def test_two_runs_give_identical_bytes(self):
        for name, topic in (("c", "b/x"), ("a", "b"), ("b", "a/y")):
            self.write(f"research/{name}.md", note(f"Note {name}", "final", topic))
        self.write(
            "ideas/i.md", note("Idea I", "seed", related=["~/notes/research/a.md"])
        )
        first = self.build()[1]
        self.assertEqual(self.build()[1], first)

    def test_file_starts_with_markmap_frontmatter(self):
        self.write("research/a.md", note("Note A", "final", "a"))
        text = self.build()[1]
        self.assertTrue(
            text.startswith(
                "---\ntitle: Notes index\nmarkmap:\n  initialExpandLevel: 2\n---\n"
            )
        )

    def test_brackets_in_titles_are_escaped(self):
        self.write("research/a.md", note("A [draft] note", "final", "a"))
        self.assertIn("- [A \\[draft\\] note](research/a.md)", self.build()[1])

    def test_quoted_title_keeps_its_hash(self):
        self.write("research/a.md", note('"Fix for issue #42"', "final", "kubernetes"))
        self.assertIn("- [Fix for issue #42](research/a.md) · final", self.lines())

    def test_note_that_is_not_utf8_does_not_stop_the_index(self):
        self.write("research/a.md", note("Note A", "final", "kubernetes"))
        (self.root / "research" / "b.md").write_bytes(
            note("Caf\xe9 note", "draft", "kubernetes").encode("latin-1")
        )
        lines = self.lines()
        self.assertIn("- [Note A](research/a.md) · final", lines)
        self.assertTrue(any(l.startswith("- [Caf") and "(research/b.md)" in l for l in lines))


if __name__ == "__main__":
    unittest.main()
