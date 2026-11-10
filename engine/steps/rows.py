"""The `rows` step: the rows of the checkpoint's walk file at the configured level, each marked `fired`
where its globs match a path of the walk, else `judge`."""
from __future__ import annotations

from matchers import rows
from stores import walks
from steps.base import TextStep


class RowsStep(TextStep):
    id = "rows"
    title = "Rows"
    always = False
    reads = (walks.ROWS,)

    def _rows(self, context):
        file = context.walk.file
        return file.rows_at(context.config.engagement) if file is not None else []

    def present(self, context):
        return bool(self._rows(context))

    def paths(self, context):
        """The paths the rows are matched against."""
        return context.walk.matched

    def data(self, context):
        lines = []
        paths = self.paths(context)
        for row in self._rows(context):
            lines.append("- **%s** (%s)" % (row["id"], rows.state(row, paths)))
            lines.append("  fires when: %s" % row["fires-when"])
            lines.append("  consult: %s" % row["consult"])
            lines.append("  owed act: %s" % row["owed act"])
        return lines


MEMBER = RowsStep
