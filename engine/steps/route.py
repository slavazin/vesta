"""The `route` step: the evidence each kind of change needs, and the order of homes a group is tried against."""
from __future__ import annotations

from steps.base import TextStep
from steps.group import prose

BARS, LADDER = "Bars", "Ladder"


class RouteStep(TextStep):
    id = "route"
    title = "Route"
    reads = (BARS, LADDER)

    def data(self, context):
        return prose(context, BARS) + [""] + prose(context, LADDER)


MEMBER = RouteStep
