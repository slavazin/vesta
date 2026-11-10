"""The YAML subset: a strict reader and the one canonical writer.

A document is a mapping. A value is a plain, quoted or folded string, an integer, `true`, `false`, an
inline list of scalars, a block list of scalars or mappings, or a nested mapping. The reader refuses
everything else and names the file and line. The writer has one form for each value, so a file it wrote
reads back and writes again byte for byte.
"""
from __future__ import annotations

import re

from kernel.errors import SubsetError

WIDTH = 100
STEP = 2
MAX_DEPTH = 4

KEY = re.compile(r"([a-z][a-z0-9-]*):(?: (.*)|)\Z")
KEY_NAME = re.compile(r"[a-z][a-z0-9-]*\Z")
INTEGER = re.compile(r"-?[0-9]+\Z")
FOLD = ">-"

_OPENERS = {
    "[": "an inline list is not allowed here",
    "]": "a value may not open with `]`",
    "{": "a `{…}` mapping on one line is not read; put each key on its own line",
    "}": "a value may not open with `}`",
    ">": "the only folded form is `>-`",
    "|": "a `|` block is not read; a value holds no line break, so put such text in the body",
    "*": "a value may not open with `*`; quote it",
    "&": "a value may not open with `&`; quote it",
    "!": "a value may not open with `!`; quote it",
    "%": "a value may not open with `%`; quote it",
    "@": "a value may not open with `@`; quote it",
    "'": "single quotes are not read; use double quotes",
    "#": "a value may not open with `#`; quote it",
    ",": "a value may not open with `,`; quote it",
}


# ---------------------------------------------------------------------------------------------- reading

class _Reader(object):
    def __init__(self, text, file, first_line, depth=MAX_DEPTH):
        if text.startswith("\ufeff"):
            text = text[1:]
        self.lines = text.replace("\r\n", "\n").split("\n")
        self.file = file
        self.first_line = first_line
        self.depth = depth
        for index, line in enumerate(self.lines):
            if "\r" in line:
                self.fail(index, "a carriage return inside a line; end lines with a line feed")

    def fail(self, index, message):
        raise SubsetError(self.file, self.first_line + index, message)

    def indent(self, index):
        line = self.lines[index]
        count = 0
        for char in line:
            if char == " ":
                count += 1
            elif char == "\t":
                self.fail(index, "a tab in indentation; indent with two spaces a level")
            else:
                break
        return count

    def skip(self, index):
        """The index of the next line that is neither blank nor a comment."""
        while index < len(self.lines):
            stripped = self.lines[index].strip(" \t")
            if stripped and not stripped.startswith("#"):
                return index
            if stripped.startswith("#"):
                self.indent(index)
            index += 1
        return index

    def document(self):
        index = self.skip(0)
        if index < len(self.lines) and self.indent(index) != 0:
            self.fail(index, "the document's keys start at the left margin")
        result, index = self.mapping(index, 0, 1, {})
        if index < len(self.lines):
            self.fail(index, "unexpected indentation")
        return result

    def mapping(self, index, indent, depth, result):
        while True:
            index = self.skip(index)
            if index >= len(self.lines):
                return result, index
            found = self.indent(index)
            if found < indent:
                return result, index
            if found > indent:
                self.fail(index, "this line is indented further than the one above allows: a nested key goes two spaces in, and a value does not continue on a second line (use `>-` for a long one)")
            index = self.entry(self.lines[index][indent:], index, indent, depth, result)

    def entry(self, content, index, indent, depth, result):
        """Read one `key: value` whose key text is `content`; return the index after the value."""
        match = KEY.match(content.rstrip(" \t"))
        if not match:
            if content.startswith("- ") or content == "-":
                self.fail(index, "a list item where a key is expected")
            if content.startswith("---") or content.startswith("..."):
                self.fail(index, "a `%s` line inside the block; the block holds one mapping and no document marks" % content[:3])
            self.fail(index, "expected `key: value` with a key matching [a-z][a-z0-9-]*")
        key, rest = match.group(1), (match.group(2) or "").strip(" \t")
        if key in result:
            self.fail(index, "the key `%s` occurs twice" % key)
        if rest == "":
            result[key], index = self.block(index, indent, depth, key)
        elif rest == FOLD:
            result[key], index = self.folded(index, indent)
        elif rest.startswith("["):
            result[key], index = self.inline_list(rest, index), index + 1
        else:
            result[key], index = self.scalar(rest, index), index + 1
        return index

    def block(self, index, indent, depth, key):
        """The nested mapping or block list under a key that has nothing after its colon."""
        child = self.skip(index + 1)
        if child < len(self.lines) and self.indent(child) == indent and self.lines[child][indent:].startswith("-"):
            self.fail(child, "indent the items of the list under `%s` by two spaces" % key)
        if child >= len(self.lines) or self.indent(child) <= indent:
            self.fail(index, "the key `%s` has no value; write `\"\"` for an empty text and `[]` for an empty list" % key)
        if self.indent(child) != indent + STEP:
            self.fail(child, "indent a nested value by two spaces")
        content = self.lines[child][indent + STEP:]
        if content.startswith("- ") or content == "-":
            return self.block_list(child, indent + STEP, depth)
        if depth + 1 > self.depth:
            self.fail(child, "mappings nest to %d levels here; this one is deeper" % self.depth)
        return self.mapping(child, indent + STEP, depth + 1, {})

    def block_list(self, index, indent, depth):
        items = []
        while True:
            index = self.skip(index)
            if index >= len(self.lines):
                return items, index
            found = self.indent(index)
            if found < indent:
                return items, index
            if found > indent:
                self.fail(index, "unexpected indentation in a list")
            content = self.lines[index][indent:]
            if content == "-":
                self.fail(index, "an empty list item")
            if not content.startswith("- "):
                self.fail(index, "expected a list item opening `- `")
            body = content[2:]
            if body.startswith(" "):
                self.fail(index, "one space follows the `-` of a list item")
            if KEY.match(body.rstrip(" \t")):
                if depth + 1 > self.depth:
                    self.fail(index, "mappings nest to %d levels here; this one is deeper" % self.depth)
                item = {}
                after = self.entry(body, index, indent + STEP, depth + 1, item)
                item, index = self.mapping(after, indent + STEP, depth + 1, item)
                items.append(item)
            else:
                body = body.strip(" \t")
                if body == "":
                    self.fail(index, "an empty list item")
                if body.startswith("["):
                    self.fail(index, "a list inside a list is not read")
                if body == FOLD:
                    self.fail(index, "a folded scalar is not allowed as a list item")
                items.append(self.scalar(body, index))
                index += 1

    def folded(self, index, indent):
        parts = []
        index += 1
        while index < len(self.lines):
            line = self.lines[index]
            if line.strip(" \t") == "":
                break
            found = self.indent(index)
            if found <= indent:
                break
            if found != indent + STEP:
                self.fail(index, "indent each line of a `>-` value by two spaces more than its key")
            parts.append(line.strip(" \t"))
            index += 1
        if not parts:
            self.fail(index - 1, "a folded scalar with no text")
        return " ".join(parts), index

    def scalar(self, text, index):
        if text.startswith('"'):
            value, end = self.quoted(text, 0, index)
            if text[end:].strip(" \t"):
                self.fail(index, "text after the closing quote")
            return value
        return self.plain(text, index)

    def plain(self, text, index):
        if text[0] in _OPENERS:
            self.fail(index, _OPENERS[text[0]])
        if text.startswith("- "):
            self.fail(index, "a value may not open with `- `; quote it")
        if ": " in text:
            self.fail(index, "a plain value may not contain `: `; quote it")
        if " #" in text:
            self.fail(index, "a plain value may not contain ` #`; there are no trailing comments")
        if INTEGER.match(text):
            return int(text)
        if text == "true":
            return True
        if text == "false":
            return False
        return text

    def quoted(self, text, start, index):
        """Read a quoted scalar opening at `start`; return (value, position after the closing quote)."""
        out = []
        position = start + 1
        while position < len(text):
            char = text[position]
            if char == "\\":
                following = text[position + 1:position + 2]
                if following not in ('"', "\\"):
                    self.fail(index, 'the only escapes in a quoted value are \\" and \\\\')
                out.append(following)
                position += 2
            elif char == '"':
                return "".join(out), position + 1
            else:
                out.append(char)
                position += 1
        self.fail(index, "a quoted value does not close on its line")

    def inline_list(self, text, index):
        if not text.endswith("]"):
            self.fail(index, "an inline list closes with `]` on its line")
        items = []
        position = 1
        end = len(text) - 1
        if text[1:end].strip(" \t") == "":
            return items
        while True:
            while position < end and text[position] in " \t":
                position += 1
            if position >= end:
                self.fail(index, "an empty item in an inline list")
            if text[position] == '"':
                value, position = self.quoted(text, position, index)
                if position > end:
                    self.fail(index, "an inline list closes with `]` on its line")
            else:
                stop = text.find(",", position, end)
                stop = end if stop < 0 else stop
                raw = text[position:stop].strip(" \t")
                if raw == "":
                    self.fail(index, "an empty item in an inline list")
                if "[" in raw or "]" in raw:
                    self.fail(index, "a list inside a list is not read; quote an item that holds a bracket")
                value = self.plain(raw, index)
                position = stop
            items.append(value)
            while position < end and text[position] in " \t":
                position += 1
            if position >= end:
                return items
            if text[position] != ",":
                self.fail(index, "items of an inline list are separated by commas")
            position += 1


def read(text, file="", first_line=1, depth=MAX_DEPTH):
    """Read a document of the subset into a dict. Raises SubsetError naming file and line.
    `depth` is how many levels mappings may nest, the document counted as the first."""
    return _Reader(text, file, first_line, depth).document()


def line_of(text, path, first_line=1):
    """The line that holds the key at a path of keys, or `first_line` where it is not found.

    Follows nested mappings by indentation. It does not look inside list items.
    """
    wanted = list(path)
    stack = []
    for index, raw in enumerate(text.replace("\r\n", "\n").split("\n")):
        stripped = raw.lstrip(" ")
        match = KEY.match(stripped.rstrip(" \t"))
        if not match or stripped.startswith("#"):
            continue
        indent = len(raw) - len(stripped)
        while stack and stack[-1][0] >= indent:
            stack.pop()
        stack.append((indent, match.group(1)))
        if [key for _, key in stack] == wanted and indent == STEP * (len(wanted) - 1):
            return first_line + index
    return first_line


# ---------------------------------------------------------------------------------------------- writing

def _is_scalar(value):
    return isinstance(value, (str, int, bool))


def _plain_legal(text, inline=False):
    if text == "" or text != text.strip():
        return False
    if text[0] in _OPENERS or text[0] == '"' or text.startswith("- ") or text == "-":
        return False
    if ": " in text or " #" in text or text.endswith(":"):
        return False
    if INTEGER.match(text) or text in ("true", "false", FOLD):
        return False
    if any(ord(char) < 32 or ord(char) == 127 for char in text):
        return False
    if inline and any(char in text for char in ',[]"'):
        return False
    return True


def _quote(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _check_string(text):
    if "\n" in text or "\r" in text:
        raise ValueError("a string that holds a line break is not representable; put such text in the body")


def _scalar(value, inline=False):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    _check_string(value)
    return value if _plain_legal(value, inline) else _quote(value)


def scalar(value):
    """One text, whole number or true/false value as it is written on a line."""
    return _scalar(value)


def _foldable(text):
    return text != "" and text == text.strip()


def _fold(text, width):
    words = text.split(" ")
    lines = []
    current = [words[0]]
    length = len(words[0])
    for previous, word in zip(words, words[1:]):
        breakable = previous != "" and word != "" and not previous.endswith("\t") and not word.startswith("\t")
        if breakable and length + 1 + len(word) > width:
            lines.append(" ".join(current))
            current = [word]
            length = len(word)
        else:
            current.append(word)
            length += 1 + len(word)
    lines.append(" ".join(current))
    return lines


def _entry(key, value, indent, depth):
    """The lines of one `key: value` at an indentation."""
    if not isinstance(key, str) or not KEY_NAME.match(key):
        raise ValueError("a key matches [a-z][a-z0-9-]*, not %r" % (key,))
    pad = " " * indent
    head = pad + key + ":"
    if isinstance(value, bool) or isinstance(value, int):
        return [head + " " + _scalar(value)]
    if isinstance(value, str):
        _check_string(value)
        if len(head) + 1 + len(value) <= WIDTH or not _foldable(value):
            return [head + " " + _scalar(value)]
        inner = " " * (indent + STEP)
        return [head + " " + FOLD] + [inner + line for line in _fold(value, WIDTH - indent - STEP)]
    if isinstance(value, dict):
        if not value:
            raise ValueError("an empty mapping is not representable (key %r)" % key)
        if depth + 1 > MAX_DEPTH:
            raise ValueError("mappings nest to %d levels (key %r)" % (MAX_DEPTH, key))
        return [head] + _mapping(value, indent + STEP, depth + 1)
    if isinstance(value, (list, tuple)):
        if all(_is_scalar(item) for item in value):
            line = head + " [" + ", ".join(_scalar(item, inline=True) for item in value) + "]"
            if len(line) <= WIDTH:
                return [line]
        lines = [head]
        inner = " " * (indent + STEP)
        for item in value:
            if _is_scalar(item):
                lines.append(inner + "- " + _scalar(item))
            elif isinstance(item, dict):
                if not item:
                    raise ValueError("an empty mapping is not representable (in list %r)" % key)
                if depth + 1 > MAX_DEPTH:
                    raise ValueError("mappings nest to %d levels (in list %r)" % (MAX_DEPTH, key))
                body = _mapping(item, indent + STEP + STEP, depth + 1)
                body[0] = inner + "- " + body[0][indent + STEP + STEP:]
                lines.extend(body)
            else:
                raise ValueError("a list holds scalars or mappings, not %r (in list %r)" % (type(item).__name__, key))
        return lines
    raise ValueError("%r is not a value of the subset (key %r)" % (type(value).__name__, key))


def _mapping(mapping, indent, depth):
    lines = []
    for key, value in mapping.items():
        lines.extend(_entry(key, value, indent, depth))
    return lines


def write(mapping):
    """Write a dict in the canonical form, keys in the dict's own order. Raises ValueError on a value
    the subset cannot hold."""
    if not isinstance(mapping, dict):
        raise ValueError("a document is a mapping")
    lines = _mapping(mapping, 0, 1)
    return "\n".join(lines) + "\n" if lines else ""


def is_canonical(text):
    """Say whether a text of the subset is in the written form."""
    return write(read(text)) == text.replace("\r\n", "\n")
