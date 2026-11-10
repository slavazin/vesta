"""What every shipped step shares: its instruction comes from its text file."""
from __future__ import annotations

from kernel import ids
from model.abstractions import Section, Step
from steps import instruction

NONE = "none"


class TextStep(Step):
    """A step that gathers lines of data and prints the instruction shipped under its id."""

    def data(self, context):
        """The lines of data; empty where the step found nothing."""
        raise NotImplementedError

    def words(self, context):
        """The words the instruction text leaves open beyond the common ones, by name."""
        return {}

    def render(self, context):
        return Section(self.title, self.data(context), instruction.of_step(context, self.id, self.words(context)))


def record_in_full(context, record):
    """A record as its file holds it, between two lines that say where it starts and ends."""
    return (
        ["---- %s, in full (%s) ----" % (record.label, record.path)]
        + context.tree.read(record.path).rstrip("\n").split("\n")
        + ["---- end of %s ----" % record.label]
    )


def titled(store, record):
    """`D-004, <title>`: a record as a sheet names it."""
    title = store.title(record)
    return "%s, %s" % (record.label, title) if title else record.label


def named(context, ref):
    """The same for a reference, or the reference itself where the record is gone."""
    found = context.stores.resolve(ref)
    if found is None:
        return "%s (no longer in the store)" % (ids.parse_ref(ref)[0] or ref)
    return titled(*found)


def minted_line(entry):
    """One observation the session wrote, from the session's own list: its label and title."""
    return "- %s, %s" % (ids.parse_ref(str(entry.get("id", "")))[0], entry.get("title", ""))
