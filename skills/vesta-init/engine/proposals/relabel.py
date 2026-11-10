"""Relabel: the records of a store renamed, with every reference and mention following.

A reference is followed by its internal id, so none breaks; this refreshes the half a person reads.
"""
from __future__ import annotations

import re

from kernel import ids
from model.abstractions import KindError
from model.record import LABEL
from model.record import UID
from proposals import proposal as proposals
from session import pending

DATED = re.compile(r"[^-]+-([0-9]{8}-[0-9a-f]{8})\Z")
LOGS = "vesta/log"
TEXT = (".md", ".jsonl")


def plan(context, store, prefix, digits, only=None):
    """[(record, new label)] for the records whose label changes. With `only`, that one record
    moves to the next free number; otherwise every record takes the store's new label form."""
    records = store.list()
    if only is not None:
        if digits <= 0:
            raise KindError("the store `%s` does not number its records, so one cannot be moved to the next number" % store.name)
        used = [record.label for record in records]
        return [(only, ids.numbered_label(prefix, digits, ids.next_number(used, prefix)))]
    found = []
    free = ids.next_number([record.label for record in records], None)
    for record in records:
        if digits > 0:
            number = ids.number_of(record.label)
            if number is None:
                number, free = free, free + 1
            new = ids.numbered_label(prefix, digits, number)
        else:
            tail = DATED.match(record.label)
            new = "%s-%s" % (prefix, tail.group(1)) if tail else ids.dated_label(prefix, context.clock.today(), record.uid)
        if new != record.label:
            found.append((record, new))
    taken = [new for _, new in found]
    if len(set(taken)) != len(taken):
        raise KindError("the new label form would give two records of `%s` the same label" % store.name)
    return found


def _files(tree, folder):
    found = []
    for name in tree.list(folder):
        path = folder + "/" + name
        if tree.is_dir(path):
            found.extend(_files(tree, path))
        elif name.endswith(TEXT):
            found.append(path)
    return found


def into(change, context, renamed):
    """Add to a Change what renaming those records takes: the files moved, the label half of every
    reference refreshed, and whole-word mentions rewritten in records, drafts, walk files and logs."""
    if not renamed:
        return change
    change.renamed.update((record.label, new) for record, new in renamed)
    tree = context.tree
    labels = dict((record.label, new) for record, new in renamed)
    by_uid = dict((record.uid, new) for record, new in renamed)
    word = re.compile(r"(?<![\w-])(%s)(?![\w-])" % "|".join(re.escape(label) for label in sorted(labels, key=len, reverse=True)))

    def reworded(text):
        return word.sub(lambda match: labels[match.group(1)], text)

    def path_of(path):
        folder, _, leaf = path.rpartition("/")
        stem, dot, rest = leaf.partition(".")
        return "%s/%s%s%s" % (folder, labels[stem], dot, rest) if stem in labels and (folder + "/").startswith(homes) else path

    # The folders whose files are named by a label of the renamed store. A decided proposal lives in
    # the log, so the log is one of them only where the proposals themselves are renamed.
    holders = set(store.name for store in pending.stores_of(context))
    homes = tuple(set(
        [record.path.rpartition("/")[0] + "/" for record, _ in renamed]
        + [proposals.LOG + "/" for record, _ in renamed if record.store in holders]
    ))
    seen = set()
    for store in context.stores.all():
        for record in store.list():
            seen.add(record.path)
            changed = record.copy()
            if record.uid in by_uid:
                changed.fields[LABEL] = by_uid[record.uid]
            for field in store.type.fields:
                if field.type in ("text", "list") and field.name not in (LABEL, UID):
                    # A label written into a text field: what a note says should have caught it, a proposal's target.
                    value = changed.fields.get(field.name)
                    if isinstance(value, str):
                        changed.fields[field.name] = reworded(value)
                    elif isinstance(value, list):
                        changed.fields[field.name] = [reworded(item) if isinstance(item, str) else item for item in value]
                if field.type not in ("ref", "refs"):
                    continue
                values = [changed.fields.get(field.name)] if field.type == "ref" else list(changed.fields.get(field.name) or [])
                fresh = []
                for value in values:
                    label, uid = ids.parse_ref(value) if isinstance(value, str) and value else (None, None)
                    if uid in by_uid and label is not None:
                        value = ids.format_ref(by_uid[uid], uid)
                    elif uid is None and label in labels:
                        value = labels[label]
                    fresh.append(value)
                changed.fields[field.name] = fresh[0] if field.type == "ref" else fresh
            changed.body = reworded(record.body)
            target = path_of(record.path)
            text = store.text(changed)
            if target != record.path:
                change.moves.append((record.path, target))
                change.writes[target] = text
            elif text != tree.read(record.path):
                change.writes[record.path] = text
    others = set(_files(tree, LOGS))
    for checkpoint in context.config.checkpoints.values():
        if tree.is_file(checkpoint.walk):
            others.add(checkpoint.walk)
    for store in context.stores.all():
        for name in tree.list(store.path):
            if name.endswith(proposals.DRAFT):
                others.add(store.path + "/" + name)
    for path in sorted(others - seen):
        before = tree.read(path)
        text, target = reworded(before), path_of(path)
        if target != path:
            change.moves.append((path, target))
            change.writes[target] = text
        elif text != before:
            change.writes[path] = text
    return change
