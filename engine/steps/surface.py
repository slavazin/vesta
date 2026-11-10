"""The `surface` step: what the session wrote down, what waits for the owner, and the reminders
that are on and met."""
from __future__ import annotations

from session import observations, pending, reminders
from steps.base import NONE, TextStep, minted_line


class SurfaceStep(TextStep):
    id = "surface"
    title = "Surface"
    live = True
    joins = True

    def data(self, context):
        session = context.walk.session
        lines = ["Observations this session wrote, by where each came from:"]
        groups = {}
        for entry in session.minted:
            groups.setdefault(str(entry.get(observations.VIA, "")), []).append(entry)
        for via in sorted(groups):
            lines.append("- %s (%d)" % (via or "no source named", len(groups[via])))
            lines.extend("  " + minted_line(entry) for entry in groups[via])
        if not groups:
            lines.append(NONE)
        lines.extend(["", "Proposals waiting for the owner's decision when this sheet was printed; `proposals` lists them as they stand after any drafted since:"])
        lines.extend(pending.lines(context) or [NONE])
        lines.extend(["", "Reminders:"])
        lines.extend(reminders.due(context) or [NONE])
        return lines


MEMBER = SurfaceStep
