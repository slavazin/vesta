"""The `offers` step: the lens answers of this session that became observations, and the test a
choice is put through. Printed at the highest engagement level only."""
from __future__ import annotations

from session import observations
from steps.base import NONE, TextStep, minted_line

CHOICES = "Choices"
LENS = "lens:"


class OffersStep(TextStep):
    id = "offers"
    title = "Offers"
    live = True
    joins = True
    needs = "conversation"
    lowest_level = "active"
    reads = (CHOICES,)

    def data(self, context):
        session = context.walk.session
        lines = ["Answers of this session that were written down:"]
        lines.extend([minted_line(entry) for entry in session.minted if str(entry.get(observations.VIA, "")).startswith(LENS)] or [NONE])
        test = context.walk.file.prose(CHOICES) if context.walk.file is not None else None
        lines.extend(["", "The test for a choice (`%s`, %s):" % (context.walk.checkpoint.walk, CHOICES), ""])
        lines.extend(test.split("\n") if test else [NONE])
        return lines


MEMBER = OffersStep
