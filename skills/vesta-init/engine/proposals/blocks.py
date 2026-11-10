"""The block forms a proposal's Change section takes, and the one way prose is changed."""
from __future__ import annotations

import re

from kernel import markdown, yamlsubset
from kernel.errors import SubsetError
from model.abstractions import KindError
from session import pending

SET, ROW, FIND, REPLACE = "vesta-set", "vesta-row", "find", "replace"
FILL = pending.FILL
DEPTH = 3


def _one(text, tag):
    found = [content for name, content, _ in markdown.fenced_blocks(text) if name == tag]
    if len(found) != 1:
        raise KindError("the Change section holds %d `%s` blocks; it takes exactly one" % (len(found), tag))
    try:
        data = yamlsubset.read(found[0], "the `%s` block" % tag, 1, depth=DEPTH)
    except SubsetError as error:
        raise KindError("the `%s` block does not read: %s" % (tag, error))
    if not isinstance(data, dict) or not data:
        raise KindError("the `%s` block names nothing" % tag)
    return data


def set_block(text):
    """The fields a `vesta-set` block names, with their whole new values."""
    return _one(text, SET)


def dotted_block(text):
    """The keys a `vesta-set` block names as dotted paths, each with its value. One key a line."""
    found = [content for name, content, _ in markdown.fenced_blocks(text) if name == SET]
    if len(found) != 1:
        raise KindError("the Change section holds %d `%s` blocks; it takes exactly one" % (len(found), SET))
    values = {}
    for line in found[0].split("\n"):
        if not line.strip():
            continue
        key, sign, rest = line.partition(":")
        key = key.strip()
        if not sign or not rest.strip() or not all(part and part.replace("-", "").replace("_", "").isalnum() for part in key.split(".")):
            raise KindError("a line of the `%s` block is `<dotted.key>: <value>`, as `reminders.learn.open-observations: 40`; this one is `%s`" % (SET, line.strip()))
        try:
            values[key] = yamlsubset.read("value:" + rest, "the `%s` block" % SET, 1)["value"]
        except SubsetError as error:
            raise KindError("the value of `%s` does not read: %s" % (key, error.message))
    if not values:
        raise KindError("the `%s` block names nothing" % SET)
    return values


def row_block(text):
    """The operation and cells a `vesta-row` block names."""
    return _one(text, ROW)


def pairs(text):
    """[(find, replace)] for the find/replace pairs of a Change section, in order."""
    blocks = [(name, content) for name, content, _ in markdown.fenced_blocks(text) if name in (FIND, REPLACE)]
    if not blocks or len(blocks) % 2:
        raise KindError("the Change section takes one or more pairs: a four-backtick `find` block, then a `replace` block")
    found = []
    for (first, find), (second, replace) in zip(blocks[0::2], blocks[1::2]):
        if first != FIND or second != REPLACE:
            raise KindError("each `find` block is followed by its `replace` block")
        find = find[:-1] if find.endswith("\n") else find
        replace = replace[:-1] if replace.endswith("\n") else replace
        if not find.strip():
            raise KindError("a `find` block is empty")
        found.append((find, replace))
    return found


def position(text, find):
    """Where a find text occurs in a text. Raises KindError unless it occurs exactly once."""
    count = text.count(find)
    if count != 1:
        raise KindError("the `find` text %s occurs %s in the target; it must occur exactly once" % (
            _short(find), "nowhere" if count == 0 else "%d times" % count))
    return text.index(find)


def replace_once(text, find, replace):
    """The text with one occurrence of `find` replaced. An empty replacement that leaves two blank
    lines in a row leaves one."""
    text = text.replace("\r\n", "\n")
    at = position(text, find)
    result = text[:at] + replace + text[at + len(find):]
    if not replace:
        result = re.sub(r"\n{3,}", "\n\n", result)
    return result


def _short(text):
    text = " ".join(text.split())
    return "`%s`" % (text if len(text) <= 60 else text[:57] + "...")
