"""Near-duplicates: records whose title and opening line share half or more of their words."""
from __future__ import annotations

import re

WORD = re.compile(r"[^\W\d_]{4,}")


def words(*texts):
    """The lower-cased words of four or more letters of some texts."""
    return set(word.lower() for text in texts for word in WORD.findall(str(text or "")))


def alike(first, second):
    """Say whether two word sets share half or more of the smaller one's words."""
    smaller = min(len(first), len(second))
    return smaller > 0 and len(first & second) * 2 >= smaller


def of_record(store, record):
    return words(store.title(record), store.type.role(record, "when"))


def covering(store, title, when, skip=()):
    """The accepted records of a store that a title and an opening line are alike to."""
    mine = words(title, when)
    return [
        record for record in store.list()
        if store.type.is_accepted(record) and record.uid not in skip and alike(mine, of_record(store, record))
    ]


def pairs(store):
    """Every pair of accepted records of a store that are alike, in label order."""
    records = [record for record in store.list() if store.type.is_accepted(record)]
    sets = [of_record(store, record) for record in records]
    found = []
    for i in range(len(records)):
        for j in range(i + 1, len(records)):
            if alike(sets[i], sets[j]):
                found.append((records[i], records[j]))
    return found
