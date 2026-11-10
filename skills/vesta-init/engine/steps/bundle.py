"""The `bundle` step: the session as it was recorded while it went."""
from __future__ import annotations

from matchers import triggers
from session import state
from steps.base import NONE, TextStep, named


class BundleStep(TextStep):
    id = "bundle"
    title = "Bundle"

    def data(self, context):
        session = context.walk.session
        lines = ["Session %s, opened %s, %s." % (session.id, session.opened, session.status)]
        if session.late:
            lines.append("It was opened late, after the work it belongs to: it has no start walk, so what was loaded and what changed are not recorded here.")
        lines.extend(["", "Tasks, in the owner's words:"])
        lines.extend(["%d. %s" % (position + 1, ask) for position, ask in enumerate(session.asks)] or [NONE])
        lines.extend(["", "Records loaded:"])
        lines.extend([
            "- %s (by %s; %s)" % (named(context, entry.get("record", "")), entry.get("by", ""), entry.get("mark") or "not marked yet")
            for entry in session.loaded
        ] or [NONE])
        lines.extend(["", "Jots, in order:"])
        lines.extend([
            "- %s %s%s%s" % (jot.get("at", ""), "[steer] " if jot.get("steer") else "", " ".join(str(jot.get("text", "")).split()), " (anchor: %s)" % jot["anchor"] if jot.get("anchor") else "")
            for jot in session.jots
        ] or [NONE])
        paths, problem = state.changed(context, session)
        lines.extend(["", "Paths changed since the session opened, less what the engine wrote:"])
        if problem:
            lines.append("could not be read: %s" % problem)
        else:
            lines.extend(["- %s" % path for path in paths] or [NONE])
        lines.extend(["", "Triggers whose probe state changed during the session:"])
        lines.extend(triggers.changed(context, context.stores.recalled(), session.probes) or [NONE])
        return lines


MEMBER = BundleStep
