"""Small helpers for reading a command's arguments."""
from __future__ import annotations

import sys

from kernel.errors import UsageError


def split(arguments, flags=(), options=(), many=(), takes=False):
    """Split arguments into (positionals, {name: value}).

    `flags` take no value; `options` take one; `many` take every following argument up to the next
    option. Positionals are refused unless `takes` is set.
    """
    positional = []
    found = {}
    rest = list(arguments)
    while rest:
        item = rest.pop(0)
        if item in flags:
            found[item] = True
        elif item in options:
            if not rest:
                raise UsageError("`%s` takes a value" % item)
            found[item] = rest.pop(0)
        elif item in many:
            values = []
            while rest and not (rest[0].startswith("--") and len(rest[0]) > 2):
                values.append(rest.pop(0))
            found[item] = values
        elif item.startswith("--") and len(item) > 2:
            raise UsageError("`%s` is not an option of this command" % item)
        else:
            positional.append(item)
    if positional and not takes:
        raise UsageError("this command takes no `%s`" % positional[0])
    return positional, found


def text(value, stdin=None):
    """A free-text argument: `-` reads it from standard input, so no shell quoting touches it."""
    if value == "-":
        return read_stdin(stdin).strip("\n")
    return value


def read_stdin(stdin=None):
    """All of standard input, as UTF-8 text."""
    try:
        return (stdin if stdin is not None else sys.stdin).read()
    except UnicodeDecodeError:
        raise UsageError("standard input is not UTF-8 text; nothing was recorded. Send the text as UTF-8 and run the command again.")
