"""The `row` kind: one row of a walk file's Rows table added, changed or removed."""
from __future__ import annotations

from model.abstractions import ProposalKind
from proposals import edits, tables, targets


class RowKind(ProposalKind):
    id = "row"
    table = tables.ROWS
    cost = "one more standing check read each time the `%s` steps are run, where a check is added; none where one is changed or removed"

    def resolve(self, target, context):
        return targets.walk_file(context, target)

    def scaffold(self, target, context, label):
        return self.table.example(self.resolve(target, context)[1])

    def validate(self, proposal, context):
        path, checkpoint = self.resolve(proposal.target, context)
        return edits.problems(lambda: self.table.read(proposal, context, path, checkpoint))

    def changes(self, proposal, context, approver):
        path, checkpoint = self.resolve(proposal.target, context)
        return self.table.change(proposal, context, path, checkpoint)

    def standing_cost(self, target, context):
        return self.cost % self.resolve(target, context)[1].id


MEMBER = RowKind
