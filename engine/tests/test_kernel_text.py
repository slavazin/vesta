import os
import unittest

import support
from kernel import frontmatter, markdown
from kernel.errors import SubsetError

FENCE3 = "`" * 3
FENCE4 = "`" * 4


class Frontmatter(unittest.TestCase):
    def test_split_and_join_round_trip(self):
        text = "---\na: 1\nb: x\n---\n# Title\n\nBody.\n"
        front, body, line = frontmatter.split(text)
        self.assertEqual((front, body, line), ("a: 1\nb: x\n", "# Title\n\nBody.\n", 5))
        self.assertEqual(frontmatter.join(front, body), text)

    def test_crlf_reads_as_lf(self):
        front, body, _ = frontmatter.split("---\r\na: 1\r\n---\r\nBody\r\n")
        self.assertEqual((front, body), ("a: 1\n", "Body\n"))

    def test_a_missing_or_unclosed_block_is_refused(self):
        for text in ("# Title\n", "---\na: 1\n# Title\n", ""):
            with self.assertRaises(SubsetError) as caught:
                frontmatter.split(text, "x.md")
            self.assertEqual(caught.exception.file, "x.md")

    def test_a_rule_line_in_the_body_is_body(self):
        _, body, _ = frontmatter.split("---\na: 1\n---\nabove\n---\nbelow\n")
        self.assertEqual(body, "above\n---\nbelow\n")


BODY = "\n".join([
    "# The title",
    "",
    "Opening lines.",
    "",
    "## Context",
    "One.",
    "",
    FENCE3 + "markdown",
    "# Not a title",
    "## Not a section",
    "| not | a table |",
    "|---|---|",
    FENCE3,
    "",
    "## Decision",
    "",
    "Two.",
    "### A sub-heading stays inside",
    "",
    "## Warrant",
    "- Three.",
    "",
])


class Sections(unittest.TestCase):
    def test_title_sections_and_preamble(self):
        doc = markdown.Document(BODY)
        self.assertEqual(doc.title, "The title")
        self.assertEqual(doc.names(), ["Context", "Decision", "Warrant"])
        self.assertEqual(doc.preamble(), "Opening lines.")
        self.assertEqual(doc.text_of(doc.section("Decision")), "Two.\n### A sub-heading stays inside")
        self.assertEqual(doc.text_of(doc.section("Warrant")), "- Three.")
        self.assertIn("## Not a section", doc.text_of(doc.section("Context")))
        self.assertIsNone(doc.section("Missing"))
        self.assertEqual(doc.section("Decision").heading, 14)

    def test_a_body_with_no_title(self):
        doc = markdown.Document("Just text.\n\n## One\nx\n")
        self.assertIsNone(doc.title)
        self.assertEqual(doc.names(), ["One"])

    def test_replace_a_section(self):
        doc = markdown.Document("# T\n\n## One\n\nold\n\n## Two\n\nkeep\n")
        self.assertEqual(doc.replace(doc.section("One"), "new\nlines"), "# T\n\n## One\n\nnew\nlines\n\n## Two\n\nkeep\n")
        self.assertEqual(doc.replace(doc.section("Two"), "new"), "# T\n\n## One\n\nold\n\n## Two\n\nnew\n")
        self.assertEqual(doc.replace(doc.section("One"), ""), "# T\n\n## One\n\n## Two\n\nkeep\n")

    def test_fenced_blocks_by_tag_outermost_only(self):
        text = "\n".join([
            "intro",
            FENCE3 + "vesta-set",
            "when: x",
            FENCE3,
            FENCE4 + "find",
            "has a",
            FENCE3 + "vesta-set",
            "inner: 1",
            FENCE3,
            FENCE4,
            "",
        ])
        self.assertEqual(markdown.fenced_blocks(text, "vesta-set"), [("vesta-set", "when: x\n", 2)])
        self.assertEqual(markdown.fenced_blocks(text, "find"), [("find", "has a\n" + FENCE3 + "vesta-set\ninner: 1\n" + FENCE3 + "\n", 5)])
        self.assertEqual([tag for tag, _, _ in markdown.fenced_blocks(text)], ["vesta-set", "find"])


class Fences(unittest.TestCase):
    def test_what_opens_a_fence_and_what_does_not(self):
        tick = FENCE3
        inline = "# T\n\n" + tick + "x" + tick + " is inline code\n\n## A\ntext\n## B\n"
        self.assertEqual(markdown.Document(inline).names(), ["A", "B"])
        tilde = "~~~\n## Not a section\n~~~\n## A\n"
        self.assertEqual(markdown.Document(tilde).names(), ["A"])
        indented = "  " + tick + "\n## Not a section\n  " + tick + "\n## A\n"
        self.assertEqual(markdown.Document(indented).names(), ["A"])
        mixed = tick + "\n~~~\n## Not a section\n" + tick + "\n## A\n"
        self.assertEqual(markdown.Document(mixed).names(), ["A"])

    def test_an_unclosed_fence_is_found_with_its_line(self):
        self.assertEqual(markdown.unclosed_fence("a\n" + FENCE3 + "vesta-schema\nlayout: flat\n"), 2)
        self.assertIsNone(markdown.unclosed_fence("a\n" + FENCE3 + "\nx\n" + FENCE3 + "\n"))
        self.assertEqual(markdown.fenced_lines([FENCE3, "x", FENCE3, "y"]), {0, 1, 2})


class Tables(unittest.TestCase):
    def test_a_row_that_does_not_close_is_refused_and_no_row_is_dropped(self):
        with self.assertRaises(SubsetError) as caught:
            markdown.read_table("| a | b |\n|---|---|\n| 1 | 2 |\n| 3 | 4\n| 5 | 6 |\n", "walks/close.md")
        self.assertEqual(caught.exception.line, 4)

    def test_a_table_round_trips_with_cells_intact(self):
        header = ["id", "fires-when", "fires-on", "consult", "owed act"]
        rows = [
            ["start-01", "the task changes how a release is cut", "`scripts/release*`", "`docs/releasing.md`", "read it"],
            ["start-02", "anything, with \\ and * and _ and é", "—", "an outside source", ""],
        ]
        text = markdown.write_table(header, rows)
        self.assertEqual(text.split("\n")[1], "|---|---|---|---|---|")
        table = markdown.read_table(text)
        self.assertEqual((table.header, table.rows), (header, rows))
        self.assertEqual(markdown.write_table(table.header, table.rows), text)
        self.assertEqual(table.records()[0]["consult"], "`docs/releasing.md`")

    def test_the_shipped_walk_tables_are_already_in_the_written_form(self):
        for name, sections in (("walks-start.md", ["Rows", "Lenses"]), ("walks-close.md", ["Rows", "Lenses"])):
            text = support.read(os.path.join(support.DATA, "verbatim", name))
            doc = markdown.Document(text)
            for section in sections:
                content = doc.text_of(doc.section(section))
                table = markdown.read_table(content)
                self.assertEqual(markdown.write_table(table.header, table.rows), content + "\n", name + " " + section)
        start = markdown.Document(support.read(os.path.join(support.DATA, "verbatim", "walks-start.md")))
        self.assertEqual(len(markdown.read_table(start.text_of(start.section("Lenses"))).rows), 3)
        close = markdown.Document(support.read(os.path.join(support.DATA, "verbatim", "walks-close.md")))
        self.assertEqual(markdown.read_table(close.text_of(close.section("Rows"))).rows, [])

    def test_a_cell_with_a_pipe_or_a_line_break_is_refused_on_write(self):
        for cell in ("a | b", "a\nb", "a\rb"):
            with self.assertRaises(ValueError):
                markdown.write_table(["x"], [[cell]])
        with self.assertRaises(ValueError):
            markdown.write_table(["x", "y"], [["only one"]])

    def test_a_row_of_the_wrong_length_is_refused_with_its_line(self):
        with self.assertRaises(SubsetError) as caught:
            markdown.read_table("| a | b |\n|---|---|\n| 1 | 2 |\n| 1 |\n", "walks/start.md", 10)
        self.assertEqual((caught.exception.file, caught.exception.line), ("walks/start.md", 13))

    def test_text_without_a_table(self):
        self.assertIsNone(markdown.read_table("no table here\n| not | one |\n"))

    def test_the_table_position_is_reported(self):
        table = markdown.read_table("intro\n\n| a |\n|---|\n| 1 |\n| 2 |\n\nafter\n")
        self.assertEqual((table.start, table.end), (2, 6))


if __name__ == "__main__":
    unittest.main()
