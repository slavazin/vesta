"""The `add` kind: a new record in a store."""
from __future__ import annotations

from model.abstractions import SUPERSEDES, KindError, ProposalKind
from proposals import proposal as proposals, records, targets


class AddKind(ProposalKind):
    id = "add"
    draft = True

    def resolve(self, target, context):
        return targets.store(context, target)

    def home(self, target, context):
        return self.resolve(target, context), []

    def scaffold(self, target, context, label):
        return records.see(label)

    def draft_text(self, target, context):
        return records.skeleton(self.resolve(target, context))

    def validate(self, proposal, context):
        store = self.resolve(proposal.target, context)
        found = records.names_draft(proposal) + proposals.draft_problems(context, proposal, store)
        role = store.type.life_field(SUPERSEDES)
        try:
            replaced = proposals.read_draft(context, proposal, store).get(role) if role else None
        except KindError:
            replaced = None
        if replaced:
            found.append("the draft: `%s` names a record, and an `add` replaces none; a record that replaces another is proposed with `propose supersede --target <id>`" % role)
        return found

    def changes(self, proposal, context, approver):
        return records.successor(context, proposal, self.resolve(proposal.target, context), approver)

    def standing_cost(self, target, context):
        return records.cost(self.resolve(target, context))


MEMBER = AddKind
