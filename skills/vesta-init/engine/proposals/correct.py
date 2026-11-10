"""The `correct` kind: wording of a record's body is put right; its title and what it requires are not touched."""
from __future__ import annotations

from kernel import frontmatter, markdown
from model.abstractions import Change, ProposalKind
from proposals import blocks, edits, prose, targets


class CorrectKind(ProposalKind):
    id = "correct"

    def resolve(self, target, context):
        return targets.record(context, target, accepted=True)

    def scaffold(self, target, context, label):
        return prose.EXAMPLE

    def _body(self, proposal, context):
        store, record = self.resolve(proposal.target, context)
        payload = store.type.payload_section

        def guard(text, start, end):
            document = markdown.Document(text)
            if document.title_index is not None and prose.spans(text, start, end, document.title_index, document.title_index + 1):
                return "lies in the title; what a record is called changes only through a `supersede` proposal"
            section = document.section(payload) if payload else None
            if section is not None and prose.spans(text, start, end, section.heading, section.end):
                return "lies in the section `## %s`; what a record requires changes only through a `supersede` proposal" % payload
            return ""

        pairs = blocks.pairs(proposal.change())
        return store, record, pairs, prose.applied(record.body, pairs, guard)

    def validate(self, proposal, context):
        return edits.problems(lambda: self._body(proposal, context))

    def changes(self, proposal, context, approver):
        store, record, pairs, body = self._body(proposal, context)
        changed = record.copy()
        changed.body = body
        change = Change(record.ref)
        change.replaced.extend(("%s, body text" % record.label, find) for find, _ in pairs)
        change.writes[record.path] = store.text(changed)
        return change

    def standing_cost(self, target, context):
        return "none"


MEMBER = CorrectKind
