"""The index projector: one block per accepted record, built from the record type's index roles.

A block says when to open a record. It never holds the title or any body text.
"""
from __future__ import annotations

from kernel import ids
from model.abstractions import RETIRED, RETIRED_BECAUSE, STATUS, SUPERSEDED, SUPERSEDED_BY

WIDTH = 100
LINES = (("when", "when:   "), ("except", "except: "), ("why", "why:    "))
INDENT = "  "
RESIDUE = (
    "This index does not show: whether a `when` line is written in the words a task arrives in — one that is "
    "not will go unrecognized, and nothing here detects that; a record with no paths is never matched "
    "mechanically. The close's sweep and the owner's corrections are where such a miss shows."
)


def _two_lines(prefix, text):
    """A role's line, wrapped once at 100 columns: the second line takes whatever is left."""
    text = " ".join(str(text).split())
    if len(prefix) + len(text) <= WIDTH:
        return [prefix + text]
    cut = text.rfind(" ", 0, WIDTH - len(prefix) + 1)
    if cut <= 0:
        return [prefix + text]
    return [prefix + text[:cut], " " * len(prefix) + text[cut + 1:]]


def live_triggers(store, record):
    """The triggers of a record that are not resolved."""
    name = store.type.role_field("triggers")
    if name is None:
        return []
    return [trigger for trigger in record.mappings(name) if not trigger.get("resolved")]


def block(store, record, triggers=False):
    """The lines of one record's index block."""
    kind = store.type
    paths = [path for path in record.texts(kind.role_field("paths")) if path.strip()] if kind.role_field("paths") else []
    lines = [record.label + ("  [" + ", ".join(paths) + "]" if paths else "")]
    for role, label in LINES:
        value = kind.role(record, role)
        if not isinstance(value, str):
            continue
        if value and role == "when":
            lines.extend(_two_lines(INDENT + label, value))
        elif value:
            lines.append(INDENT + label + " ".join(str(value).split()))
    if triggers:
        for trigger in live_triggers(store, record):
            lines.append("%sunstable-if (%s): %s" % (INDENT, trigger.get("id", ""), trigger.get("if", "")))
    return lines


def pointer(store, record):
    """The one line that stands for a record no longer in force."""
    kind = store.type
    status = kind.life(record, STATUS)
    if status == SUPERSEDED:
        return "%s  %s by %s" % (record.label, status, ids.parse_ref(str(kind.life(record, SUPERSEDED_BY) or ""))[0] or "?")
    if status == RETIRED:
        return "%s  %s: %s" % (record.label, status, kind.life(record, RETIRED_BECAUSE) or "")
    return "%s  not in force (status: %s)" % (record.label, status if isinstance(status, str) and status else "none")


def project(store, everything=False, triggers=False):
    """The index of a store as a list of blocks, each a list of lines, in label order."""
    blocks = []
    for record in store.list():
        if store.type.is_accepted(record):
            blocks.append(block(store, record, triggers))
        elif everything:
            blocks.append([pointer(store, record)])
    return blocks
