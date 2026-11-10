"""The `pointer-block` check: the block in the project's agent-instruction file is the shipped one."""
from __future__ import annotations

from kernel.finding import ERROR, Finding
from model.abstractions import Check

SHIPPED = "pointer-block.md"
WHERE = "vesta/.engine/templates/" + SHIPPED
START, END = "<!-- vesta:start -->", "<!-- vesta:end -->"
LIMIT = 15


def block_of(text):
    """(the block with its two marker lines, its 1-based line) or (None, 1) where the markers are not both there."""
    lines = text.split("\n")
    start = end = None
    for index, line in enumerate(lines):
        if line.strip() == START and start is None:
            start = index
        elif line.strip() == END and start is not None:
            end = index
            break
    if start is None or end is None:
        return None, 1
    return "\n".join(lines[start:end + 1]) + "\n", start + 1


class PointerBlockCheck(Check):
    id = "pointer-block"
    residue = "not whether an agent follows it"

    def run(self, context):
        path = context.config.pointer_file
        if not path:
            return []
        try:
            present = context.tree.is_file(path)
        except ValueError:
            present = False
        if not present:
            return [Finding(ERROR, self.id, path, 1, "`pointer-file` names this path and no file is there")]
        try:
            block, line = block_of(context.tree.read(path))
        except UnicodeDecodeError:
            return [Finding(ERROR, self.id, path, 1, "this file is not UTF-8 text, so the Vesta block cannot be read in it")]
        if block is None:
            return [Finding(ERROR, self.id, path, 1, "the Vesta block is not in this file between its `%s` and `%s` lines, each on a line of its own; add the text of %s" % (START, END, WHERE))]
        found = []
        text = context.tree.read(path)
        if len([each for each in text.split("\n") if each.strip() == START]) > 1:
            found.append(Finding(ERROR, self.id, path, line, "the Vesta block is in this file more than once; keep one"))
        try:
            shipped = context.shipped.read(SHIPPED)
        except OSError:
            return found + [Finding(ERROR, self.id, WHERE, 1, "this copy of the engine lacks the block's text; copy the engine into vesta/.engine again")]
        if block != shipped:
            found.append(Finding(ERROR, self.id, path, line, "the Vesta block differs from the one this engine ships; replace it, markers included, with the text of %s" % WHERE))
        if len(block.rstrip("\n").split("\n")) > LIMIT:
            found.append(Finding(ERROR, self.id, path, line, "the Vesta block is longer than %d lines" % LIMIT))
        return found


MEMBER = PointerBlockCheck
