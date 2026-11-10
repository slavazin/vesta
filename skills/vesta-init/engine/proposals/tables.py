"""What the `row` and `lens` kinds share: one row of a walk file's table added, changed or removed."""
from __future__ import annotations

import re

from kernel import markdown
from model import config as configuration
from model.abstractions import Change, KindError
from proposals import blocks
from stores import walks

OPS = ("add", "change", "remove")
OP = "op"
ORIGIN = "origin"
LEVEL = "level"
NUMBER = re.compile(r"-([0-9]+)\Z")


def _cell(value, name):
    if not isinstance(value, str):
        raise KindError("the cell `%s` must be text" % name)
    if "|" in value or "\n" in value:
        raise KindError("the cell `%s` may not hold `|` or a line break" % name)
    return value.strip()


def _line(cells):
    return "| " + " | ".join(cells) + " |"


class TableEdit(object):
    """One table of walk files, by its section, its columns, and the column that names a row."""

    def __init__(self, section, columns, key, cells=None):
        self.section = section
        self.columns = columns
        self.key = key
        # The keys of a `vesta-row` block, each with the column it fills.
        self.cells = cells or dict((column, column) for column in columns if column != ORIGIN)

    def example(self, checkpoint):
        lines = ["```%s" % blocks.ROW, "%s: add" % OP]
        for name in self.cells:
            if name == self.key == "id":
                continue  # the engine gives a new row its id
            lines.append('%s: "%s"' % (name, "%s %s>" % (blocks.FILL, name) if name != LEVEL else "standard"))
        return "\n".join(lines + ["```"])

    def _rows(self, file):
        return file.rows if self.section == walks.ROWS else file.lenses

    def _next_id(self, file, checkpoint):
        used = [int(match.group(1)) for match in (NUMBER.search(row[self.key]) for row in self._rows(file)) if match]
        return "%s-%02d" % (checkpoint.id, max(used + [0]) + 1)

    def read(self, proposal, context, path, checkpoint):
        """(operation, the row's key, the new cells by column, the walk file). Raises KindError."""
        block = blocks.row_block(proposal.change())
        file = walks.read(context.tree, path)
        if file.problems:
            raise KindError("%s does not read: %s" % (path, file.problems[0][1]))
        if file.document.section(self.section) is None:
            raise KindError("%s has no `## %s` section" % (path, self.section))
        op = block.get(OP)
        if op not in OPS:
            raise KindError("`%s` is one of: %s" % (OP, ", ".join(OPS)))
        for name in block:
            if name != OP and name not in self.cells:
                raise KindError("`%s` is not a cell of this table; the cells are: %s" % (name, ", ".join(self.cells)))
        given = dict((self.cells[name], _cell(value, name)) for name, value in block.items() if name != OP)
        existing = dict((row[self.key], row) for row in self._rows(file))
        key = given.get(self.key, "")
        if op == "add":
            if self.key == "id":
                if key:
                    raise KindError("the engine assigns a new row's `id`; leave it empty")
                key = self._next_id(file, checkpoint)
            elif not key:
                raise KindError("a new row names its `%s`" % self.key)
            if key in existing:
                raise KindError("%s already has a row `%s`" % (path, key))
            cells = dict((column, given.get(column, "")) for column in self.columns)
            cells[self.key] = key
            cells[ORIGIN] = proposal.label
            for column in self.columns:
                if not cells[column]:
                    raise KindError("a new row gives every cell; `%s` is empty%s" % (
                        [n for n, c in self.cells.items() if c == column][0], " (write `%s` where the row fires on no path)" % walks.JUDGED if column == "fires-on" else ""))
        else:
            if key not in existing:
                raise KindError("%s has no row `%s`; its rows are: %s" % (path, key or "(none named)", ", ".join(existing) or "none"))
            cells = dict((column, existing[key][column]) for column in self.columns)
            if op == "change":
                changed = dict((column, value) for column, value in given.items() if column != self.key)
                if not changed:
                    raise KindError("a `change` names the cells that change")
                cells.update(changed)
        if "fires-on" in cells and op != "remove":
            cells["fires-on"] = _globs(cells["fires-on"])
        if cells.get(LEVEL) not in configuration.LEVELS:
            raise KindError("`%s` is one of: %s" % (LEVEL, ", ".join(configuration.LEVELS)))
        return op, key, cells, file

    def change(self, proposal, context, path, checkpoint):
        op, key, cells, file = self.read(proposal, context, path, checkpoint)
        lines = markdown.lines_of(file.text)
        rows = self._rows(file)
        header = (file.rows_line if self.section == walks.ROWS else file.lenses_line) - 1
        change = Change(path[len("vesta/"):])
        new = _line([cells[column] for column in self.columns])
        if op == "add":
            at = (rows[-1]["line"] if rows else header + 2)
            lines.insert(at, new)
        else:
            at = [row["line"] for row in rows if row[self.key] == key][0] - 1
            change.replaced.append(("%s, the row `%s`" % (path, key), lines[at]))
            if op == "change":
                lines[at] = new
            else:
                del lines[at]
        change.writes[path] = "\n".join(lines)
        return change


def _globs(cell):
    """A `fires-on` cell in the table's form: `—`, or each glob in backticks."""
    if cell in ("", walks.JUDGED):
        return walks.JUDGED
    if walks.globs_of(cell) is not None:
        return cell
    parts = [part.strip().strip("`") for part in cell.split(",") if part.strip()]
    return ", ".join("`%s`" % part for part in parts)


ROWS = TableEdit(walks.ROWS, walks.ROW_COLUMNS, "id", {
    "id": "id", "fires-when": "fires-when", "fires-on": "fires-on", "consult": "consult", "owed-act": "owed act", LEVEL: LEVEL,
})
LENSES = TableEdit(walks.LENSES, walks.LENS_COLUMNS, "lens")
