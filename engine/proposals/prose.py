"""What the kinds that change prose share: find/replace pairs applied to one text."""
from __future__ import annotations

from model.abstractions import KindError
from proposals import blocks

EXAMPLE = "````%s\n%s the text to replace, exactly as it stands; it must occur once>\n````\n````%s\n%s the text that takes its place>\n````" % (
    blocks.FIND, blocks.FILL, blocks.REPLACE, blocks.FILL)


def applied(text, pairs, guard=None):
    """(the text with every pair applied in order, [(find, what it replaced)]). `guard(text, start,
    end)` returns why a span may not be touched, or nothing."""
    text = text.replace("\r\n", "\n")
    for find, replace in pairs:
        at = blocks.position(text, find)
        if guard is not None:
            reason = guard(text, at, at + len(find))
            if reason:
                raise KindError("the `find` text %s %s" % (blocks._short(find), reason))
        text = blocks.replace_once(text, find, replace)
    return text


def spans(text, start, end, first, last):
    """Say whether a span of characters touches the lines first..last (0-based, last excluded)."""
    lines = text.split("\n")
    offset = 0
    for index, line in enumerate(lines):
        line_end = offset + len(line)
        if first <= index < last and start <= line_end and end > offset:
            return True
        offset = line_end + 1
    return False
