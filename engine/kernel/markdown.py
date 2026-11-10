"""Markdown as the engine reads it: the title, `##` sections, fenced blocks, and pipe tables.

Headings and tables inside a fenced block are text, not structure.
"""
from __future__ import annotations

import re

from kernel.errors import SubsetError

FENCE = re.compile(r" {0,3}(`{3,}|~{3,})(.*)\Z")
SEPARATOR = re.compile(r"\|(\s*:?-+:?\s*\|)+\s*\Z")


def lines_of(text):
    return text.replace("\r\n", "\n").split("\n")


def _scan(lines):
    """Yield (index, line, inside a fence, (tag, opening index) when the line closes a fence)."""
    opened = None
    for index, line in enumerate(lines):
        match = FENCE.match(line)
        if match and opened is None and match.group(1)[0] == "`" and "`" in match.group(2):
            match = None
        if opened is None:
            if match:
                opened = (match.group(1), match.group(2).strip(), index)
                yield index, line, True, None
            else:
                yield index, line, False, None
        else:
            fence, tag, start = opened
            if match and match.group(1)[0] == fence[0] and len(match.group(1)) >= len(fence) and match.group(2).strip() == "":
                opened = None
                yield index, line, True, (tag, start)
            else:
                yield index, line, True, None


def fenced_lines(lines):
    """The indexes of the lines that open, close or lie inside a fenced block."""
    return set(index for index, _, inside, _ in _scan(lines) if inside)


def unclosed_fence(text):
    """The 1-based line of a fence that is opened and never closed, or None."""
    lines = lines_of(text)
    opened = None
    for index, line, inside, closed in _scan(lines):
        if inside and closed is None and opened is None:
            opened = index
        elif closed is not None:
            opened = None
    return None if opened is None else opened + 1


class Section(object):
    """One `## ` section: its name, the index of its heading line, and the indexes of its content."""

    __slots__ = ("name", "heading", "start", "end")

    def __init__(self, name, heading, start, end):
        self.name = name
        self.heading = heading
        self.start = start
        self.end = end


class Document(object):
    """A Markdown text split at its `# ` title and `## ` headings."""

    def __init__(self, text):
        self.lines = lines_of(text)
        self.title = None
        self.title_index = None
        self.sections = []
        heads = []
        for index, line, fenced, _ in _scan(self.lines):
            if fenced:
                continue
            if line.startswith("# ") and self.title is None and not heads:
                self.title = line[2:].strip()
                self.title_index = index
            elif line.startswith("## "):
                heads.append((line[3:].strip(), index))
        for position, (name, index) in enumerate(heads):
            end = heads[position + 1][1] if position + 1 < len(heads) else len(self.lines)
            self.sections.append(Section(name, index, index + 1, end))

    def section(self, name):
        """The first section of that name, or None."""
        for section in self.sections:
            if section.name == name:
                return section
        return None

    def names(self):
        return [section.name for section in self.sections]

    def text_of(self, section):
        """A section's content, without its heading and without blank lines at either end."""
        return "\n".join(self.lines[section.start:section.end]).strip("\n")

    def preamble(self):
        """The text between the title and the first section."""
        start = 0 if self.title_index is None else self.title_index + 1
        end = self.sections[0].heading if self.sections else len(self.lines)
        return "\n".join(self.lines[start:end]).strip("\n")

    def replace(self, section, content):
        """The whole text with a section's content replaced. One blank line follows the heading and
        one precedes the next heading."""
        body = content.strip("\n").split("\n") if content.strip("\n") else []
        head = self.lines[:section.start] + [""] + body
        tail = self.lines[section.end:]
        if body and tail:
            head.append("")
        return "\n".join(head + (tail if tail else [""]))


def fenced_blocks(text, tag=None):
    """Return [(tag, content, 1-based line of the opening fence)] for each fenced block, outermost only.
    With a tag, only blocks of that tag."""
    lines = lines_of(text)
    found = []
    for index, _, _, closed in _scan(lines):
        if closed is None:
            continue
        name, start = closed
        if tag is None or name == tag:
            content = "\n".join(lines[start + 1:index])
            found.append((name, content + "\n" if content else "", start + 1))
    return found


class Table(object):
    """A pipe table: its header cells, its rows of cells, and the line indexes it spans in its text."""

    __slots__ = ("header", "rows", "start", "end")

    def __init__(self, header, rows, start=0, end=0):
        self.header = list(header)
        self.rows = [list(row) for row in rows]
        self.start = start
        self.end = end

    def column(self, name):
        return self.header.index(name)

    def records(self):
        """Each row as a dict keyed by the header."""
        return [dict(zip(self.header, row)) for row in self.rows]


def _cells(line):
    inner = line.strip()
    if not (inner.startswith("|") and inner.endswith("|") and len(inner) >= 2):
        return None
    return [cell.strip() for cell in inner[1:-1].split("|")]


def read_table(text, file="", first_line=1):
    """Read the first pipe table of a text, or return None where it has none.

    Raises SubsetError where a row's cell count differs from the header's.
    """
    lines = lines_of(text)
    fenced = dict((index, inside) for index, _, inside, _ in _scan(lines))
    for index in range(len(lines) - 1):
        if fenced[index] or fenced[index + 1]:
            continue
        header = _cells(lines[index])
        if header is None or not SEPARATOR.match(lines[index + 1].strip()):
            continue
        if len(_cells(lines[index + 1])) != len(header):
            raise SubsetError(file, first_line + index + 1, "the separator row has a different number of cells from the header")
        rows = []
        end = index + 2
        while end < len(lines) and not fenced[end]:
            cells = _cells(lines[end])
            if cells is None:
                if lines[end].strip().startswith("|"):
                    raise SubsetError(file, first_line + end, "a table row closes with `|`")
                break
            if len(cells) != len(header):
                raise SubsetError(file, first_line + end, "a table row has %d cells; the header has %d" % (len(cells), len(header)))
            rows.append(cells)
            end += 1
        return Table(header, rows, index, end)
    return None


def write_table(header, rows):
    """The text of a table: one space of padding, columns not aligned. Raises ValueError for a cell
    that holds `|` or a line break, or a row of the wrong length."""
    out = []
    for cells in [list(header)] + [list(row) for row in rows]:
        if len(cells) != len(header):
            raise ValueError("a row has %d cells; the header has %d" % (len(cells), len(header)))
        for cell in cells:
            if "|" in cell or "\n" in cell or "\r" in cell:
                raise ValueError("a table cell may not hold `|` or a line break: %r" % (cell,))
        out.append("| " + " | ".join(cell.strip() for cell in cells) + " |")
    out.insert(1, "|" + "---|" * len(header))
    return "\n".join(out) + "\n"
