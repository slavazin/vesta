"""The glob matcher for paths.

`*` matches within one path segment, `?` one character of a segment, and a segment that is exactly `**`
matches any number of segments, none included. Everything else is literal. Paths use `/`.
"""
from __future__ import annotations

import re


def _segments(text):
    parts = [part for part in text.split("/") if part not in ("", ".")]
    return parts


def _segment_pattern(segment):
    out = []
    for char in segment:
        if char == "*":
            out.append("[^/]*")
        elif char == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(char))
    return re.compile("".join(out) + r"\Z")


def match(pattern, path):
    """Say whether a path matches a glob."""
    wanted = _segments(pattern)
    given = _segments(path.replace("\\", "/"))
    compiled = [None if part == "**" else _segment_pattern(part) for part in wanted]
    seen = {}

    def walk(i, j):
        key = (i, j)
        if key in seen:
            return seen[key]
        if i == len(compiled):
            result = j == len(given)
        elif compiled[i] is None:
            result = walk(i + 1, j) or (j < len(given) and walk(i, j + 1))
        else:
            result = j < len(given) and bool(compiled[i].match(given[j])) and walk(i + 1, j + 1)
        seen[key] = result
        return result

    return walk(0, 0)


def has_wildcard(text):
    return "*" in text or "?" in text
