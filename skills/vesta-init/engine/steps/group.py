"""The `group` step: how the project says notes are grouped, and the owner's question where one was given."""
from __future__ import annotations

from steps.base import NONE, TextStep

SHAPES = "Shapes"


def prose(context, name):
    """A prose section of the walk file under a line saying where it is from."""
    text = context.walk.file.prose(name) if context.walk.file is not None else None
    return ["%s (`%s`):" % (name, context.walk.checkpoint.walk), ""] + (text.split("\n") if text else [NONE])


class GroupStep(TextStep):
    id = "group"
    title = "Group"
    reads = (SHAPES,)

    def data(self, context):
        asks = context.walk.session.asks
        return prose(context, SHAPES) + ["", "The owner's question: %s" % (asks[-1] if asks else NONE)]


MEMBER = GroupStep
