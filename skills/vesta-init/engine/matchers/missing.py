"""The probe `missing <path>`: fires where the path is not in the project."""
from __future__ import annotations

from matchers import paths
from model.abstractions import Matcher


class MissingProbe(Matcher):
    id = "missing"

    def parse(self, subject):
        return paths.inside(subject)

    def match(self, subject, context):
        path = self.parse(subject)
        return not context.tree.exists(paths.guarded(context.tree, path))


MEMBER = MissingProbe
