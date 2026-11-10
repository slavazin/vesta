"""Observations: what a session mints at its close, and the one count a session reads of them.

The store they go to is found by what its records are, never by its name: a store whose records carry
a disposition is one a session mints into. A project with one such store needs to say nothing; with
several, the command names the one it means.
"""
from __future__ import annotations

import json

from kernel import ids
from kernel import tree as trees
from kernel.errors import Refusal, UsageError
from matchers import probes
from model.abstractions import DISPOSITION, OPEN, MatchError
from model.record import LABEL, UID, Record
from stores import conditions
from stores.filestore import ARCHIVE
from stores.schema import FILE as SCHEMA_FILE

TITLE, BODY = "title", "body"
DATE, SESSION, HELD = "date", "session", "held"
RECHECK = "recheck"
VIA, STEER_KIND = "via", "steer-kind"
PASS_FOLDER = "pass-%03d"


def stores_of(context):
    """The stores a session mints into: those whose records carry a disposition."""
    return [store for store in context.stores.all() if store.type.life_field(DISPOSITION) is not None]


def store_of(context, name=None):
    """The store a command means: the one named, else the one there is. Raises UsageError."""
    found = stores_of(context)
    names = ", ".join("`%s`" % store.name for store in found) or "none"
    if name:
        for store in found:
            if store.name == name:
                return store
        raise UsageError("`%s` is not a store that takes observations; this project has: %s" % (name, names))
    if len(found) == 1:
        return found[0]
    if not found:
        raise UsageError(
            "this project has no store that takes observations: none of the stores in vesta/vesta.yml has a "
            "`disposition` field in its SCHEMA.md"
        )
    raise UsageError("several stores take observations (%s); say which with `--store <name>`" % names)


def usable(store):
    """Refuse a store whose schema lacks a field the engine fills by name."""
    lacking = [name for name in (DATE, SESSION, HELD) if store.type.field(name) is None]
    if lacking:
        raise UsageError(
            "%s names no field %s. The engine fills the fields `%s`, `%s` and `%s` of an observation by those names, "
            "so a store that takes observations keeps them." % (schema_path(store), " or ".join("`%s`" % name for name in lacking), DATE, SESSION, HELD)
        )
    return store


def supplied(store):
    """The fields the engine fills, which an item sent to `obs add` therefore leaves out."""
    return (UID, LABEL, DATE, SESSION, store.type.life_field(DISPOSITION), HELD)


def asked(store):
    """The keys of one item sent to `obs add`, in order: the title, the body, then each field the
    engine does not fill."""
    own = supplied(store)
    return [TITLE, BODY] + [field.name for field in store.type.fields if field.name not in own]


def shape(store):
    """One item of the `obs add` input with every key it may hold, as a line of JSON."""
    return "{" + ", ".join('"%s": "…"' % name for name in asked(store)) + "}"


def schema_path(store):
    return "%s/%s" % (store.path, SCHEMA_FILE)


def is_open(store, record):
    return store.type.life(record, DISPOSITION) == OPEN


def open_count(context):
    """How many observations are open and held by no pass. The one figure a session reads of them."""
    count = 0
    for store in stores_of(context):
        for record in store.list():
            if is_open(store, record) and not record.texts(HELD):
                count += 1
    return count


def _items(text):
    try:
        items = json.loads(text.lstrip("\ufeff"))
    except RecursionError:
        raise UsageError("the input is nested too deeply to be read. `obs add` reads a JSON array of flat items from standard input.")
    except ValueError as error:
        raise UsageError("the input is not JSON (%s). `obs add` reads a JSON array of items from standard input." % error)
    if not isinstance(items, list) or not items:
        raise UsageError("the input is not a JSON array with one item or more. `obs add` reads `[{…}, {…}]` from standard input.")
    return items


def _record(context, store, session, item, taken):
    """(the record built from one item, the problems found before the schema is asked)."""
    found = []
    if not isinstance(item, dict):
        return None, ["the item is not a JSON object"]
    keys = asked(store)
    for key in item:
        if key not in keys:
            found.append("`%s` is not a key of an item; the keys are %s" % (key, ", ".join(keys)))
    for key in keys:
        value = item.get(key, "")
        field = store.type.field(key)
        if field is not None and field.type in ("list", "refs"):
            if not (isinstance(value, list) and all(isinstance(part, str) for part in value)) and value != "":
                found.append("`%s` must be a list of texts, as [\"a\", \"b\"]" % key)
        elif not isinstance(value, str):
            found.append("`%s` must be text" % key)
    if found:
        return None, found
    title = " ".join(item.get(TITLE, "").split())
    if not title:
        found.append("`%s` is empty" % TITLE)
    if not item.get(BODY, "").strip():
        found.append("`%s` is empty" % BODY)
    uid = ids.new_uid(store.name, context.clock.timestamp(), title, taken[UID])
    if store.settings.digits > 0:
        label = ids.numbered_label(store.settings.prefix, store.settings.digits, ids.next_number(taken[LABEL], store.settings.prefix))
    else:
        label = ids.dated_label(store.settings.prefix, context.clock.today(), uid)
    taken[UID].append(uid)
    taken[LABEL].append(label)
    fields = dict((name, item[name].strip() if isinstance(item.get(name, ""), str) else item[name]) for name in keys[2:] if name in item)
    fields.update({UID: uid, LABEL: label, DATE: context.clock.today(), SESSION: session.id, HELD: []})
    fields[store.type.life_field(DISPOSITION)] = OPEN
    for field in store.type.fields:
        value = fields.get(field.name)
        if field.type == "ref" and value:
            named = context.stores.resolve(value)
            if named is None:
                found.append("`%s` is `%s`, which names no record; `index --all` lists the records" % (field.name, value))
            else:
                fields[field.name] = named[1].ref
    record = Record(store.name, store.path_for(label), fields, "# %s\n\n%s\n" % (title, item.get(BODY, "").strip()))
    return record, found


def _recheck_problem(context, text):
    """Why a `recheck` cannot stand, or an empty text."""
    try:
        probes.parse(text, context)
    except MatchError as error:
        return "`%s` does not read as a probe: %s" % (RECHECK, error)
    state = probes.evaluate(text, context)
    if state.state == probes.FIRED:
        return "`%s` fires already (`%s`); it must be false now, so that it fires when the noticing matters again" % (RECHECK, text)
    if state.state == probes.ERROR:
        return "`%s` cannot be evaluated: %s" % (RECHECK, state.reason)
    return ""


def add(context, store, session, text):
    """Mint every item of a JSON array, or none. Returns the records written, in the order sent."""
    items = _items(text)
    held = store.list()
    taken = {UID: [record.uid for record in held], LABEL: [record.label for record in held]}
    records, failures = [], []
    for position, item in enumerate(items, 1):
        record, found = _record(context, store, session, item, taken)
        if record is not None:
            found.extend(problem.message for problem in conditions.problems(record, store, context) if problem.message not in found)
            if record.get(RECHECK):
                problem = _recheck_problem(context, record.get(RECHECK))
                found.extend([problem] if problem else [])
            if not found and context.tree.exists(record.path):
                found = ["%s is already there" % record.path]
            if not found:
                try:
                    store.text(record).encode("utf-8")
                except (ValueError, UnicodeError) as error:
                    found = ["it cannot be written as sent: %s" % error]
        if found:
            name = item.get(TITLE) if isinstance(item, dict) and isinstance(item.get(TITLE), str) and item.get(TITLE).strip() else "no title"
            failures.extend("item %d (%s): %s" % (position, " ".join(name.split())[:80], message) for message in found)
        records.append(record)
    if failures:
        raise Refusal(
            "nothing was written, because %d of the %d item%s cannot stand as sent:\n%s\nCorrect %s and send the whole array again."
            % (len(set(line.split(" ", 2)[1] for line in failures)), len(items), "" if len(items) == 1 else "s",
               "\n".join("- " + line for line in failures), "it" if len(items) == 1 else "them"),
            schema_path(store),
        )
    overlay = trees.Overlay(context.tree)
    for record in records:
        overlay.write(record.path, store.text(record))
    overlay.commit()
    return records


def note(session, store, records):
    """Add the records a session minted to its own list, and to the paths the engine wrote for it."""
    for record in records:
        entry = {"id": record.ref, TITLE: store.title(record)}
        entry.update((field.name, record.get(field.name)) for field in store.type.fields if field.type == "enum" and record.get(field.name))
        session.minted.append(entry)
        session.written.append(record.path)


def one_line(store, record):
    """An observation's frontmatter in one line: its label, then each field that is filled."""
    own = (UID, LABEL)
    parts = [record.label]
    for field in store.type.fields:
        value = record.get(field.name)
        if field.name in own or value in ("", [], None):
            continue
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value)
        parts.append("%s: %s" % (field.name, ids.parse_ref(str(value))[0] if field.type == "ref" else value))
    return " · ".join(parts)


def form(store, record):
    """The one-line-plus-body form: the line above, the title, then the body."""
    title = store.title(record)
    body = record.body.split("\n")
    if body and body[0].startswith("# "):
        body = body[1:]
    text = "\n".join(body).strip()
    return [one_line(store, record), "  %s" % (title or "(no title)")] + ["    " + line if line else "" for line in text.split("\n") if text]


def listed(store, which=OPEN, number=None):
    """The records of a store that are open, of one pass's archive, or all of them."""
    records = store.list()
    if which == OPEN:
        return [record for record in records if is_open(store, record)]
    if which == ARCHIVE:
        folder = "%s/%s/%s/" % (store.path, ARCHIVE, PASS_FOLDER % number)
        return [record for record in records if record.path.startswith(folder)]
    return records
