"""The walk files: the registers holding a checkpoint's project-owned rows and lenses."""
from __future__ import annotations

import re

from kernel import markdown
from kernel.errors import SubsetError
from model import config

ROWS = "Rows"
LENSES = "Lenses"
ROW_COLUMNS = ["id", "fires-when", "fires-on", "consult", "owed act", "level", "origin"]
LENS_COLUMNS = ["lens", "angle", "counterfactual", "level", "origin"]
LEVELS = config.LEVELS
JUDGED = "—"
SEED = "seed"
BACKTICKED = re.compile(r"`([^`]+)`")
LENS_NAME = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*\Z")


def globs_of(cell):
    """The globs of a `fires-on` cell, or None where it does not read: `—`, or globs in backticks
    separated by commas."""
    cell = cell.strip()
    if cell == JUDGED:
        return []
    parts = [part.strip() for part in cell.split(",")]
    found = []
    for part in parts:
        match = re.match(r"`([^`]+)`\Z", part)
        if not match:
            return None
        found.append(match.group(1))
    return found


def consult_paths(cell):
    """The backticked paths of a `consult` cell."""
    return BACKTICKED.findall(cell)


class WalkFile(object):
    """One walk file as read: its rows, its lenses, its prose sections, and what did not read."""

    def __init__(self, path, text):
        self.path = path
        self.text = text
        self.document = markdown.Document(text)
        self.problems = []
        self.rows, self.rows_line = self._table(ROWS, ROW_COLUMNS)
        self.lenses, self.lenses_line = self._table(LENSES, LENS_COLUMNS)

    def _table(self, name, columns):
        section = self.document.section(name)
        if section is None:
            return [], 1
        content = "\n".join(self.document.lines[section.start:section.end])
        first = section.start + 1
        try:
            table = markdown.read_table(content, self.path, first)
        except SubsetError as error:
            self.problems.append((error.line, error.message))
            return [], first
        if table is None:
            return [], first
        if table.header != columns:
            self.problems.append((first + table.start, "the %s table has the columns %s; they are %s" % (name, ", ".join(table.header), ", ".join(columns))))
            return [], first
        records = []
        for offset, cells in enumerate(table.rows):
            record = dict(zip(columns, cells))
            record["line"] = first + table.start + 2 + offset
            records.append(record)
        return records, first + table.start

    def prose(self, name):
        """The text of a prose section, or None where the file has none of that name."""
        section = self.document.section(name)
        return None if section is None else self.document.text_of(section)

    def rows_at(self, level):
        return [row for row in self.rows if reached(row.get("level"), level)]

    def lenses_at(self, level):
        return [lens for lens in self.lenses if reached(lens.get("level"), level)]


def reached(item_level, configured):
    """Say whether a row or lens of a level is walked at the configured engagement level."""
    if item_level not in LEVELS or configured not in LEVELS:
        return False
    return LEVELS.index(item_level) <= LEVELS.index(configured)


def read(tree, path):
    """The walk file at a path, or None where there is no such file."""
    if not tree.is_file(path):
        return None
    return WalkFile(path, tree.read(path))
