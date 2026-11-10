"""The `steers` step: the owner's corrections every configured capture source gathered; then, for
every record in force, its label and the line saying when to open it, and nothing else of it."""
from __future__ import annotations

from steps.base import NONE, TextStep

TABLE = "capture"


class SteersStep(TextStep):
    id = "steers"
    title = "Steers"
    needs = "conversation"

    def data(self, context):
        session = context.walk.session
        lines = ["Corrections captured while the session ran:"]
        captured = []
        for name in context.config.capture:
            if name not in context.known.get(TABLE, ()):
                continue
            for steer in context.member(TABLE, name)().steers(session):
                captured.append("- %s %s%s (from %s)" % (
                    steer.get("at", ""), steer.get("text", ""),
                    " (anchor: %s)" % steer["anchor"] if steer.get("anchor") else "", name,
                ))
        lines.extend(captured or [NONE])
        lines.extend(["", "Records in force, for naming the one that should have caught a correction:"])
        listed = []
        for store in context.stores.recalled():
            role = store.type.role_field("when")
            for record in store.list():
                if store.type.is_accepted(record):
                    said = " ".join(str(record.get(role) if role else "").split())
                    listed.append("- %s  %s: %s" % (record.label, role or "when", said or "(empty)"))
        lines.extend(listed or [NONE])
        return lines


MEMBER = SteersStep
