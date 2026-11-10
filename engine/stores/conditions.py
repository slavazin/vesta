"""The named conditions a schema block may list. Each reads one record and returns its problems.

A condition is registered here under the name a schema block uses; `name:argument` passes the argument.
"""
from __future__ import annotations

from kernel import ids, markdown
from kernel.finding import ERROR
from model.abstractions import (
    DISPOSITION, OPEN, RETIRED, RETIRED_BECAUSE, STATUS, SUPERSEDED, SUPERSEDED_BY, SUPERSEDES,
)
from model.record import Problem
from stores.filestore import ARCHIVE
from stores.filestore import OPEN as OPEN_FOLDER

FALSIFIER = "- False if:"


def _body_lines(record):
    """(line number in the file, text) for each body line outside a fenced block."""
    document = markdown.Document(record.body)
    fenced = markdown.fenced_lines(document.lines)
    return [(record.body_line + index, line) for index, line in enumerate(document.lines) if index not in fenced]


def falsifiers(record):
    """What each `False if:` line of a record's body says, in order."""
    found = [line[len(FALSIFIER):].strip() for _, line in _body_lines(record) if line.startswith(FALSIFIER)]
    return [text for text in found if text]


def falsifier_or_trigger(record, store, context, argument):
    if not store.type.is_accepted(record):
        return []
    if falsifiers(record):
        return []
    name = store.type.role_field("triggers")
    if name is not None and record.mappings(name):
        return []
    return [Problem(ERROR, record.body_line, "an accepted record states what would make it wrong: a `%s` line, or a trigger" % FALSIFIER)]


def successor_pair(record, store, context, argument):
    kind = store.type
    named = kind.life(record, SUPERSEDED_BY)
    if kind.life(record, STATUS) != SUPERSEDED or not named:
        return []
    found = context.stores.resolve(str(named))
    if found is None:
        return [Problem(ERROR, 2, "`%s` names %s, which is not a record" % (kind.life_field(SUPERSEDED_BY), named))]
    other, successor = found
    field = other.type.life_field(SUPERSEDES)
    back = [ids.parse_ref(text) for text in successor.texts(field)] if field else []
    if not any(uid == record.uid or (uid is None and label == record.label) for label, uid in back):
        return [Problem(ERROR, 2, "%s does not name this record as one it replaces%s" % (successor.label, " (in its `%s`)" % field if field else ""))]
    return []


def retired_reason(record, store, context, argument):
    kind = store.type
    if kind.life(record, STATUS) == RETIRED and not kind.life(record, RETIRED_BECAUSE):
        return [Problem(ERROR, 2, "a retired record says why%s" % (" in `%s`" % kind.life_field(RETIRED_BECAUSE) if kind.life_field(RETIRED_BECAUSE) else ""))]
    return []


def _text_after_title(record):
    document = markdown.Document(record.body)
    start = 0 if document.title_index is None else document.title_index + 1
    return "\n".join(document.lines[start:]).strip()


def body_max(record, store, context, argument):
    limit = int(argument)
    length = len(_text_after_title(record))
    if length > limit:
        return [Problem(ERROR, record.body_line, "the body is %d characters; the most is %d" % (length, limit))]
    return []


def no_labels(record, store, context, argument):
    labels = [label for label in argument.split(",") if label]
    found = []
    for number, line in _body_lines(record):
        for label in labels:
            if line.lstrip().startswith(label):
                found.append(Problem(ERROR, number, "a line of the body opens `%s`; a record of this store states what happened and proposes nothing" % label))
    return found


def archive_agrees(record, store, context, argument):
    name = store.type.life_field(DISPOSITION)
    if name is None:
        return []
    folder = record.path[len(store.path) + 1:].split("/", 1)[0]
    is_open = record.get(name) == OPEN
    if folder == OPEN_FOLDER and not is_open:
        return [Problem(ERROR, 2, "the record is under `%s/` and its `%s` is not `%s`" % (OPEN_FOLDER, name, OPEN))]
    if folder == ARCHIVE and is_open:
        return [Problem(ERROR, 2, "the record is under `%s/` and its `%s` is `%s`" % (ARCHIVE, name, OPEN))]
    return []


CONDITIONS = {
    "falsifier-or-trigger": falsifier_or_trigger,
    "successor-pair": successor_pair,
    "retired-reason": retired_reason,
    "body-max": body_max,
    "no-labels": no_labels,
    "archive-agrees": archive_agrees,
}


def problems(record, store, context):
    """Every problem of one record: against its type, then against each condition the type lists."""
    found = list(store.type.validate(record))
    for condition, argument in usable(store.type):
        found.extend(condition(record, store, context, argument))
    return found


def usable(record_type):
    """The (function, argument) of each condition of a type that is registered and whose argument reads."""
    bad = set(message.split("`")[1] for message in unknown(record_type))
    return [(CONDITIONS[name], argument) for name, argument in record_type.conditions if name in CONDITIONS and name not in bad]


def unknown(record_type):
    """The condition names of a record type that are not registered, or whose argument does not read."""
    found = []
    for name, argument in record_type.conditions:
        if name not in CONDITIONS:
            found.append("the condition `%s` is not one this engine has; it has %s" % (name, ", ".join(sorted(CONDITIONS))))
        elif name == "body-max" and not (argument.isdigit() and int(argument) > 0):
            found.append("`body-max` takes a number of characters above zero, as `body-max:600`")
        elif name == "no-labels" and not argument:
            found.append("`no-labels` takes the labels, as `no-labels:Fix:,TODO:`")
    return found
