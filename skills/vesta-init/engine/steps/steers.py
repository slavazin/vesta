"""The `steers` step: the owner's corrections every configured capture source gathered; then, for
every record in force, its label and the line saying when to open it, and nothing else of it."""
from __future__ import annotations

from session import settings
from steps.base import NONE, TextStep

TABLE = "capture"


class SteersStep(TextStep):
    id = "steers"
    title = "Steers"
    needs = "conversation"

    def data(self, context):
        session = context.walk.session
        lines = ["Corrections captured while the session ran:"]
        captured, more = [], []
        for name in context.config.capture:
            if name in context.known.get(TABLE, ()):
                captured.extend(context.member(TABLE, name)().lines(session, context))
        lines.extend(captured or [NONE])
        # What this person's settings add: sources the project's configuration does not name.
        for name in settings.turned_on(context, TABLE):
            if name in context.known.get(TABLE, ()) and name not in context.config.capture:
                more.extend(context.member(TABLE, name)().lines(session, context))
        for name, value, why in settings.fallen(context, TABLE):
            more.append("The setting `%s` is `%s` on this machine, and that cannot be done here: %s. Nothing was read back from the conversation: "
                        "go through it as you hold it." % (name, value, why))
        return lines + ([""] + more if more else []) + [""] + in_force(context)


def in_force(context):
    """Every record in force, by its label and the line saying when to open it, under one heading."""
    listed = []
    for store in context.stores.recalled():
        role = store.type.role_field("when")
        for record in store.list():
            if store.type.is_accepted(record):
                said = " ".join(str(record.get(role) if role else "").split())
                listed.append("- %s  %s: %s" % (record.label, role or "when", said or "(empty)"))
    return ["Records in force, for naming the one that should have caught a correction:"] + (listed or [NONE])


MEMBER = SteersStep
