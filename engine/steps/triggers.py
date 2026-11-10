"""The `triggers` step: every live trigger of every recalled store, once, with the state of its probe."""
from __future__ import annotations

from matchers import triggers
from session import state
from steps.base import TextStep


def lines_of(found):
    lines = []
    for item in found:
        lines.append("- **%s**, probe: %s" % (item.name, item.state.text()))
        lines.append("  if: %s" % " ".join(str(item.trigger.get("if", "")).split()))
        lines.append("  then: %s" % " ".join(str(item.trigger.get("then", "")).split()))
    return lines


class TriggersStep(TextStep):
    id = "triggers"
    title = "Triggers"

    def data(self, context):
        found = triggers.live(context, context.stores.recalled())
        session = context.walk.session
        fresh = dict((item.key, item.state.state) for item in found if item.key not in session.probes)
        if fresh:
            session.probes.update(fresh)
            state.save(context.tree, session)
        return lines_of(found)


MEMBER = TriggersStep
