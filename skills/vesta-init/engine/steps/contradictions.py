"""The `contradictions` step: what each loaded and swept record says would make it wrong, and the
triggers whose probe changed state while the session ran."""
from __future__ import annotations

from matchers import triggers
from session import sweep
from steps.base import NONE, TextStep, titled
from stores import conditions


class ContradictionsStep(TextStep):
    id = "contradictions"
    title = "Contradictions"
    needs = "conversation"

    def data(self, context):
        session = context.walk.session
        records = sweep.loaded(context, session) + sweep.missed(context, session)[0]
        lines = []
        for store, record in records:
            own = ["  False if: %s" % text for text in conditions.falsifiers(record)]
            for item in triggers.of_record(store, record, context):
                own.append("  trigger %s, probe: %s" % (item.trigger.get("id", ""), item.state.text()))
                own.append("    if: %s" % " ".join(str(item.trigger.get("if", "")).split()))
                own.append("    then: %s" % " ".join(str(item.trigger.get("then", "")).split()))
            lines.append("- **%s**" % titled(store, record))
            lines.extend(own or ["  states no `False if:` line and has no live trigger"])
        if not lines:
            lines.append("No record was loaded or found by the sweep.")
        lines.extend(["", "Triggers whose probe state changed during the session:"])
        lines.extend(triggers.changed(context, context.stores.recalled(), session.probes) or [NONE])
        return lines


MEMBER = ContradictionsStep
