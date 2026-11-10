"""The `notices` step: what is waiting for the owner. It prints `none` where nothing is."""
from __future__ import annotations

from session import pending, reminders
from steps.base import TextStep


class NoticesStep(TextStep):
    id = "notices"
    title = "Notices"

    def data(self, context):
        lines = []
        if context.config.remind_pending:
            waiting = pending.lines(context)
            if waiting:
                lines.append("Proposals waiting for the owner's decision:")
                lines.extend(waiting)
        return lines + reminders.due(context)


MEMBER = NoticesStep
