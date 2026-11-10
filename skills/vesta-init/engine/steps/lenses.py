"""The `lenses` step: the lenses of the checkpoint's walk file at the configured level."""
from __future__ import annotations

from steps.base import TextStep
from stores import walks


class LensesStep(TextStep):
    id = "lenses"
    title = "Lenses"
    always = False
    reads = (walks.LENSES,)
    needs = "conversation"

    def _lenses(self, context):
        file = context.walk.file
        return file.lenses_at(context.config.engagement) if file is not None else []

    def present(self, context):
        return bool(self._lenses(context))

    def data(self, context):
        lines = []
        for lens in self._lenses(context):
            lines.append("- **%s**" % lens["lens"])
            lines.append("  angle: %s" % lens["angle"])
            lines.append("  counterfactual: %s" % lens["counterfactual"])
        return lines


MEMBER = LensesStep
