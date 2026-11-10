"""The `resolve-trigger` kind: a trigger that has been dealt with says how, and is live no longer."""
from __future__ import annotations

from model.abstractions import Change, KindError, ProposalKind
from proposals import blocks, edits, targets

RESOLVED = "resolved"


class ResolveTriggerKind(ProposalKind):
    id = "resolve-trigger"

    def resolve(self, target, context):
        return targets.trigger(context, target)

    def scaffold(self, target, context, label):
        return "```%s\n%s: %s what was done about the trigger>\n```" % (blocks.SET, RESOLVED, blocks.FILL)

    def _values(self, proposal, context):
        store, record, trigger_id = self.resolve(proposal.target, context)
        values = edits.named(proposal, [RESOLVED], "a `resolve-trigger` proposal names only")
        if not isinstance(values.get(RESOLVED), str) or not values[RESOLVED].strip():
            raise KindError("`%s` says what was done about the trigger" % RESOLVED)
        return store, record, trigger_id, values[RESOLVED].strip()

    def validate(self, proposal, context):
        return edits.problems(lambda: self._values(proposal, context))

    def changes(self, proposal, context, approver):
        store, record, trigger_id, text = self._values(proposal, context)
        changed = record.copy()
        for item in changed.mappings(store.type.role_field("triggers")):
            if item.get("id") == trigger_id:
                item[RESOLVED] = text
        change = Change(record.ref)
        change.replaced.append(("%s/%s, `%s`" % (record.label, trigger_id, RESOLVED), "(empty)"))
        change.writes[record.path] = store.text(changed)
        return change

    def standing_cost(self, target, context):
        return "none: one condition fewer read at every start"


MEMBER = ResolveTriggerKind
