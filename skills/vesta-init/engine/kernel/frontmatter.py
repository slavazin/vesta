"""The frontmatter splitter: a record file is a `---` block of the YAML subset, then a Markdown body."""
from __future__ import annotations

from kernel.errors import SubsetError

MARK = "---"


def split(text, file=""):
    """Return (frontmatter text, body text, the 1-based line the body starts on).

    Raises SubsetError where the file does not open with a closed frontmatter block.
    """
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].rstrip(" \t") != MARK:
        raise SubsetError(file, 1, "a record opens with a `---` line")
    for index in range(1, len(lines)):
        if lines[index].rstrip(" \t") == MARK:
            front = "\n".join(lines[1:index])
            front = front + "\n" if front else ""
            return front, "\n".join(lines[index + 1:]), index + 2
    raise SubsetError(file, 1, "the frontmatter block is not closed by a second `---` line")


def join(front, body):
    """The file text for a frontmatter text and a body."""
    if front and not front.endswith("\n"):
        front += "\n"
    return MARK + "\n" + front + MARK + "\n" + body
