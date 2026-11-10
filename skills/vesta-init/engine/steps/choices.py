"""The `choices` step: what the owner chose in this session, the test a choice is put through, and
the records in force it is read against."""
from __future__ import annotations

from session import observations
from steps.base import NONE, TextStep, minted_line
from stores.schema import FILE as SCHEMA_FILE

CHOICES = "Choices"
CHOICE = "choice"


class ChoicesStep(TextStep):
    id = "choices"
    title = "Choices"
    live = True
    needs = "conversation"
    reads = (CHOICES,)

    def data(self, context):
        session = context.walk.session
        lines = ["What the owner chose in this session, as written down:"]
        lines.extend([minted_line(entry) for entry in session.minted if entry.get(observations.STEER_KIND) == CHOICE] or [NONE])
        test = context.walk.file.prose(CHOICES) if context.walk.file is not None else None
        lines.extend(["", "The test for a choice (`%s`, %s):" % (context.walk.checkpoint.walk, CHOICES), ""])
        lines.extend(test.split("\n") if test else [NONE])
        lines.extend(["", "Records in force:"])
        listed = []
        for store in context.stores.recalled():
            role = store.type.role_field("when")
            for record in store.list():
                if store.type.is_accepted(record):
                    listed.append("- %s  %s: %s" % (record.label, role or "when", " ".join(str(record.get(role) if role else "").split()) or "(empty)"))
        lines.extend(listed or [NONE])
        lines.extend(["", "How to write a record of each store:"])
        lines.extend(["- `%s`: `%s/%s`" % (store.name, store.path, SCHEMA_FILE) for store in context.stores.recalled()] or [NONE])
        return lines

    def words(self, context):
        stores = context.stores.recalled()
        return {"store": stores[0].name if stores else "<store>"}


MEMBER = ChoicesStep
