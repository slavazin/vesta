"""The `merge` kind: one successor written and every record it replaces flipped, together."""
from __future__ import annotations

from model.abstractions import ProposalKind
from proposals import proposal as proposals, records, targets


class MergeKind(ProposalKind):
    id = "merge"
    draft = True

    def resolve(self, target, context):
        return targets.records(context, target)

    def home(self, target, context):
        found = self.resolve(target, context)
        return found[0][0], [record for _, record in found]

    def scaffold(self, target, context, label):
        return records.see(label)

    def draft_text(self, target, context):
        found = self.resolve(target, context)
        return records.skeleton(found[0][0], [record for _, record in found])

    def validate(self, proposal, context):
        found = self.resolve(proposal.target, context)
        store = found[0][0]
        return (
            records.names_draft(proposal)
            + proposals.draft_problems(context, proposal, store)
            + records.replaces_problems(context, proposal, store, [record for _, record in found])
        )

    def changes(self, proposal, context, approver):
        found = self.resolve(proposal.target, context)
        return records.successor(context, proposal, found[0][0], approver, [record for _, record in found])

    def standing_cost(self, target, context):
        count = len(self.resolve(target, context))
        return "none: %d short blocks become one at every start" % count


MEMBER = MergeKind
