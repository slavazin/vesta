"""The `gate` step: every proposal waiting for the owner, with why it is proposed and the case against it."""
from __future__ import annotations

from kernel import markdown
from session import pending
from steps.base import NONE, TextStep

WHY, COUNTER = "Why", "Counter-case"


class GateStep(TextStep):
    id = "gate"
    title = "Gate"
    live = True
    needs = "conversation"

    def data(self, context):
        lines = []
        for store, record in pending.pending(context):
            evidence = len(record.texts(pending.EVIDENCE))
            lines.extend(["" if lines else None, pending.line(store, record, context.clock)])
            lines.append("  evidence: %d note%s · sessions they come from: %s · drafted by: %s" % (
                evidence, "" if evidence == 1 else "s", record.get(pending.SESSIONS) if record.get(pending.SESSIONS) not in ("", None) else "not stated",
                record.get(pending.SOURCE) or "not stated",
            ))
            document = markdown.Document(record.body)
            for name in (WHY, COUNTER):
                section = document.section(name)
                text = document.text_of(section).strip() if section is not None else ""
                lines.append("  %s:" % name)
                lines.extend(["    " + line if line else "" for line in (text or NONE).split("\n")])
        return [line for line in lines if line is not None]


MEMBER = GateStep
