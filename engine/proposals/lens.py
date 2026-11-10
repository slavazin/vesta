"""The `lens` kind: one row of a walk file's Lenses table added, changed or removed."""
from __future__ import annotations

from proposals import tables
from proposals.row import RowKind


class LensKind(RowKind):
    id = "lens"
    table = tables.LENSES
    cost = "one more question answered each time the `%s` steps are run, where a question is added; none where one is changed or removed"


MEMBER = LensKind
