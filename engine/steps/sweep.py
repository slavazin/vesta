"""The `sweep` step: the records that cover a changed path and were never loaded, each in full."""
from __future__ import annotations

from session import sweep
from steps.base import TextStep, record_in_full


class SweepStep(TextStep):
    id = "sweep"
    title = "Sweep"
    needs = "conversation"

    def data(self, context):
        found, problem = sweep.missed(context, context.walk.session)
        if problem:
            return ["The changed paths could not be read (%s), so no record was looked for." % problem]
        lines = []
        for _, record in found:
            if lines:
                lines.append("")
            lines.extend(record_in_full(context, record))
        return lines


MEMBER = SweepStep
