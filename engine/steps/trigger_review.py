"""The `trigger-review` step, printed only where asked for: every live trigger and every line saying
what would make a record in force wrong."""
from __future__ import annotations

from matchers import triggers
from session import passes
from steps.base import NONE, TextStep
from steps.triggers import lines_of
from stores import conditions


class TriggerReviewStep(TextStep):
    id = "trigger-review"
    title = "Trigger review"
    on_request = True
    needs = "conversation"

    def data(self, context):
        found = context.walk.session
        if not found.reviewed or self.id not in found.requested:
            found.data["trigger-review"] = True
            if self.id not in found.requested:
                found.requested.append(self.id)
            passes.save(context.tree, found)
        stores = context.stores.recalled()
        lines = ["Live triggers, each with what its probe finds now:"]
        lines.extend(lines_of(triggers.live(context, stores)) or [NONE])
        lines.extend(["", "What would make each record in force wrong:"])
        said = []
        for store in stores:
            for record in store.list():
                if store.type.is_accepted(record):
                    said.extend("- %s: False if: %s" % (record.label, text) for text in conditions.falsifiers(record))
        lines.extend(said or [NONE])
        return lines


MEMBER = TriggerReviewStep
