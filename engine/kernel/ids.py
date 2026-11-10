"""Identity: the internal id, the label, and the reference that joins them."""
from __future__ import annotations

import hashlib
import os
import re

UID = re.compile(r"[0-9a-f]{8}\Z")
REF = re.compile(r"(?P<label>[^@\s]+)@(?P<uid>[0-9a-f]{8})\Z")
NUMBERED = re.compile(r"(?P<prefix>[^-]+)-(?P<number>[0-9]+)\Z")
NEW = "NEW"


def new_uid(store, timestamp, title, taken=(), random=os.urandom):
    """Eight hexadecimal characters, drawn again while the store already holds the value."""
    taken = set(taken)
    while True:
        digest = hashlib.sha256()
        for part in (store, timestamp, title):
            digest.update(part.encode("utf-8"))
            digest.update(b"\0")
        digest.update(random(16))
        uid = digest.hexdigest()[:8]
        if uid not in taken:
            return uid


def numbered_label(prefix, digits, number):
    """`D-004` from a prefix, a minimum digit count and a number."""
    return "%s-%s" % (prefix, str(number).zfill(digits))


def dated_label(prefix, date, uid):
    """`O-20260314-a3f29c0e`: the form of a store whose label has `digits: 0`."""
    return "%s-%s-%s" % (prefix, date.replace("-", ""), uid)


def number_of(label, prefix=None):
    """The number a numbered label ends with, or None. With a prefix, only labels of that prefix count."""
    match = NUMBERED.match(label)
    if not match:
        return None
    if prefix is not None and match.group("prefix") != prefix:
        return None
    return int(match.group("number"))


def next_number(labels, prefix):
    """One above the highest number the labels of a prefix have used."""
    used = [number_of(label, prefix) for label in labels]
    return max([number for number in used if number is not None] + [0]) + 1


def sort_key(label):
    """Sorts numbered labels by their number (`D-999` before `D-1000`), the rest by their text."""
    match = NUMBERED.match(label)
    if match:
        return (match.group("prefix"), 0, int(match.group("number")), label)
    return (label, 1, 0, label)


def format_ref(label, uid):
    """`D-003@7f3a9c2e`: the label for the person, the internal id for the engine."""
    return "%s@%s" % (label, uid)


def parse_ref(text):
    """Split what names a record into (label or None, internal id or None).

    Accepts the joined form, a bare internal id, or a bare label.
    """
    text = text.strip()
    match = REF.match(text)
    if match:
        return match.group("label"), match.group("uid")
    if UID.match(text):
        return None, text
    return text, None


def trigger_ref(record, trigger):
    """`<record>/t1`: how a trigger is named from outside its record."""
    return "%s/%s" % (record, trigger)


def split_trigger_ref(text):
    """(record part, trigger id) of `<record>/t1`, or (text, None) where there is no trigger part."""
    if "/" in text:
        record, trigger = text.rsplit("/", 1)
        if re.match(r"t[0-9]+\Z", trigger):
            return record, trigger
    return text, None
