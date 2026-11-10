"""The `retire` kind: a record leaves force, with the reason."""
from __future__ import annotations

from model.abstractions import RETIRED, RETIRED_BECAUSE, STATUS, KindError, ProposalKind
from proposals import blocks, edits, targets


class RetireKind(ProposalKind):
    id = "retire"

    def resolve(self, target, context):
        store, record = targets.record(context, target, accepted=True)
        if store.type.life_field(STATUS) is None or store.type.life_field(RETIRED_BECAUSE) is None:
            raise KindError("the store `%s` has no fields for a record's status and the reason it was retired" % store.name)
        return store, record

    def scaffold(self, target, context, label):
        store, _ = self.resolve(target, context)
        return "```%s\n%s: \"%s why the record no longer holds>\"\n```" % (blocks.SET, store.type.life_field(RETIRED_BECAUSE), blocks.FILL)

    def _values(self, proposal, context):
        store, record = self.resolve(proposal.target, context)
        reason = store.type.life_field(RETIRED_BECAUSE)
        values = edits.named(proposal, [reason], "a `retire` proposal names only")
        if not isinstance(values.get(reason), str) or not values[reason].strip():
            raise KindError("`%s` says why the record is retired" % reason)
        values[store.type.life_field(STATUS)] = RETIRED
        return store, record, values

    def validate(self, proposal, context):
        return edits.problems(lambda: self._values(proposal, context))

    def changes(self, proposal, context, approver):
        return edits.rewritten(*self._values(proposal, context))

    def standing_cost(self, target, context):
        return "none: one short block fewer at every start"


MEMBER = RetireKind
