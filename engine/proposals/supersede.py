"""The `supersede` kind: a successor written and the record it replaces flipped, together."""
from __future__ import annotations

from model.abstractions import ProposalKind
from proposals import proposal as proposals, records, targets


class SupersedeKind(ProposalKind):
    id = "supersede"
    draft = True

    def resolve(self, target, context):
        return targets.record(context, target, accepted=True)

    def home(self, target, context):
        store, record = self.resolve(target, context)
        return store, [record]

    def scaffold(self, target, context, label):
        return records.see(label)

    def draft_text(self, target, context):
        store, record = self.resolve(target, context)
        return records.skeleton(store, [record], record)

    def validate(self, proposal, context):
        store, record = self.resolve(proposal.target, context)
        return (
            records.names_draft(proposal)
            + proposals.draft_problems(context, proposal, store)
            + records.replaces_problems(context, proposal, store, [record])
        )

    def changes(self, proposal, context, approver):
        store, record = self.resolve(proposal.target, context)
        return records.successor(context, proposal, store, approver, [record])

    def standing_cost(self, target, context):
        return "none: one record takes the place of another"


MEMBER = SupersedeKind
