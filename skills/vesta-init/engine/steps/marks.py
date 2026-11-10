"""The `marks` step: each loaded record that has no mark yet."""
from __future__ import annotations

from steps.base import TextStep, named


class MarksStep(TextStep):
    id = "marks"
    title = "Marks"
    needs = "conversation"

    def data(self, context):
        return [
            "- %s (loaded by %s)" % (named(context, entry.get("record", "")), entry.get("by", ""))
            for entry in context.walk.session.loaded if not entry.get("mark")
        ]


MEMBER = MarksStep
