"""The live triggers of the records in force, each with the state of its probe."""
from __future__ import annotations

from kernel import ids
from matchers import index, probes


class Live(object):
    """One live trigger: its record, its own fields, and what its probe found."""

    def __init__(self, store, record, trigger, state):
        self.store = store
        self.record = record
        self.trigger = trigger
        self.state = state

    @property
    def name(self):
        """`D-004/t1`: how the trigger is shown."""
        return ids.trigger_ref(self.record.label, str(self.trigger.get("id", "")))

    @property
    def key(self):
        """`7f3a9c2e/t1`: how the engine's state names it, which a relabel does not change."""
        return ids.trigger_ref(self.record.uid, str(self.trigger.get("id", "")))


def of_record(store, record, context, evaluate=True):
    found = []
    for trigger in index.live_triggers(store, record):
        state = probes.evaluate(trigger.get("probe", ""), context) if evaluate else probes.State(probes.NONE)
        found.append(Live(store, record, trigger, state))
    return found


def live(context, stores):
    """Every live trigger of the accepted records of those stores, in label order."""
    found = []
    for store in stores:
        for record in store.list():
            if store.type.is_accepted(record):
                found.extend(of_record(store, record, context))
    return found


def changed(context, stores, saved):
    """One line for each live trigger whose probe state differs from the state saved earlier."""
    found = []
    for item in live(context, stores):
        before = saved.get(item.key)
        if before is not None and before != item.state.state:
            found.append("- %s: %s at the start, now %s" % (item.name, before, item.state.text()))
    return found
