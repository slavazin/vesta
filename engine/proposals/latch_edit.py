"""The `latch-edit` kind: the fields that say how a record is found are rewritten; what it decides is not."""
from __future__ import annotations

from model.abstractions import LIFECYCLE, ROLES, ProposalKind
from proposals import blocks, edits, targets


def allowed(store):
    """The fields this kind may rewrite: those that play an index role, and the reference lists
    that play no part in a record's lifecycle."""
    kind = store.type
    life = set(kind.life_field(role) for role in LIFECYCLE)
    found = [kind.role_field(role) for role in ROLES if kind.role_field(role)]
    found += [field.name for field in kind.fields if field.type == "refs" and field.name not in life]
    return found


class LatchEditKind(ProposalKind):
    id = "latch-edit"

    def resolve(self, target, context):
        return targets.record(context, target, accepted=True)

    def scaffold(self, target, context, label):
        store, record = self.resolve(target, context)
        return "```%s\n%s the fields to rewrite, each with its whole new value; they may be: %s>\n```" % (blocks.SET, blocks.FILL, ", ".join(allowed(store)))

    def _values(self, proposal, context):
        store, record = self.resolve(proposal.target, context)
        return store, record, edits.named(proposal, allowed(store), "this kind rewrites only the fields that say how a record is found")

    def validate(self, proposal, context):
        return edits.problems(lambda: self._values(proposal, context))

    def changes(self, proposal, context, approver):
        return edits.rewritten(*self._values(proposal, context))

    def standing_cost(self, target, context):
        return "none, unless it adds a condition for revisiting: then one more condition read at every start"


MEMBER = LatchEditKind
