"""The proposals waiting for the owner: found, as every store is, by what its records are.

A store whose records carry an outcome holds proposals; one with an empty outcome is pending.
"""
from __future__ import annotations

import datetime

from kernel.errors import UsageError
from model.abstractions import OUTCOME

# Where a decided proposal is kept, and what the file of a draft ends with.
LOG = "vesta/log/proposals"
DRAFT = ".draft.md"
# What opens a part of a proposal its drafter has yet to write.
FILL = "<fill:"
KIND, TARGET, DRAFTED, SOURCE, EVIDENCE, SESSIONS, COST = "kind", "target", "drafted", "source", "evidence", "sessions", "standing-cost"


def stores_of(context):
    return [store for store in context.stores.all() if store.type.life_field(OUTCOME) is not None]


def store_of(context):
    """The one store that holds proposals. Raises UsageError where there is none."""
    found = stores_of(context)
    if not found:
        raise UsageError("this project has no store that holds proposals: none of the stores in vesta/vesta.yml has an `outcome` field in its SCHEMA.md")
    return found[0]


def pending(context):
    """[(store, record)] for every proposal not yet decided, in label order."""
    return [(store, record) for store in stores_of(context) for record in store.list() if not store.type.life(record, OUTCOME)]


def age(record, clock):
    """How long ago a proposal was drafted, in words."""
    try:
        days = (datetime.date.fromisoformat(clock.today()) - datetime.date.fromisoformat(str(record.get(DRAFTED)))).days
    except ValueError:
        return "of unknown age"
    if days <= 0:
        return "drafted today"
    return "drafted %d day%s ago" % (days, "" if days == 1 else "s")


def line(store, record, clock):
    """One pending proposal in one line: label, kind and target, title, standing cost, age."""
    title = store.title(record) or "(no title)"
    if FILL in title:
        title = "(still being drafted: not ready for a decision)"
    return "- %s · %s %s · %s · standing cost: %s · %s" % (
        record.label, record.get(KIND), record.get(TARGET), title, record.get(COST) or "not stated", age(record, clock),
    )


def lines(context):
    return [line(store, record, context.clock) for store, record in pending(context)]
