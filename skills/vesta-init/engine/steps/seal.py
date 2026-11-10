"""The `seal` step: the notes of the pass that are still open, each with whether a waiting proposal
cites it and how many passes have kept it open."""
from __future__ import annotations

from session import observations, passes
from steps.base import TextStep


class SealStep(TextStep):
    id = "seal"
    title = "Seal"
    live = True

    def data(self, context):
        found = context.walk.session
        cited = passes.citing(context)
        lines = []
        for store, record in passes.still_open(context, found):
            held = len(record.texts(observations.HELD))
            labels = cited.get(record.uid)
            said = "evidence of %s, which waits for the owner" % ", ".join(labels) if labels else "cited by no waiting proposal"
            fate = "kept open" if labels and held < passes.HOLD_LIMIT else "archived as read unless named"
            if held >= passes.HOLD_LIMIT:
                fate = "kept open %d times already: archived as read unless named" % held
            lines.append("- %s · %s · %s · kept open by %d earlier pass%s · at the seal: %s" % (
                record.label, store.title(record) or "(no title)", said, held, "" if held == 1 else "es", fate,
            ))
        return lines

    def words(self, context):
        return {"pass": context.walk.session.id, "keys": ", ".join("`%s:`" % key for key in passes.NOTE_KEYS), "waiting": passes.WAITING}


MEMBER = SealStep
