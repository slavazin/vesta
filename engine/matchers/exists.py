"""The probe `exists <path>`: fires where the path is in the project."""
from __future__ import annotations

from matchers import paths
from model.abstractions import Matcher


class ExistsProbe(Matcher):
    id = "exists"

    def parse(self, subject):
        return paths.inside(subject)

    def match(self, subject, context):
        path = self.parse(subject)
        return context.tree.exists(paths.guarded(context.tree, path))


MEMBER = ExistsProbe
