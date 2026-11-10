"""The `language` kind: the writing rules, or the prose of a walk file, changed by find/replace pairs."""
from __future__ import annotations

from model.abstractions import Change, ProposalKind
from proposals import blocks, edits, prose, targets


def _table_guard(text, start, end):
    lines = text.split("\n")
    for index, line in enumerate(lines):
        if line.lstrip().startswith("|") and prose.spans(text, start, end, index, index + 1):
            return "lies in a table; a table changes through a `row` or a `lens` proposal"
    return ""


class LanguageKind(ProposalKind):
    id = "language"

    def resolve(self, target, context):
        return targets.prose_file(context, target)

    def scaffold(self, target, context, label):
        return prose.EXAMPLE

    def _text(self, proposal, context):
        path, checkpoint = self.resolve(proposal.target, context)
        pairs = blocks.pairs(proposal.change())
        return path, pairs, prose.applied(context.tree.read(path), pairs, _table_guard if checkpoint is not None else None)

    def validate(self, proposal, context):
        return edits.problems(lambda: self._text(proposal, context))

    def changes(self, proposal, context, approver):
        path, pairs, text = self._text(proposal, context)
        change = Change(path[len("vesta/"):])
        change.replaced.extend(("%s, text" % path, find) for find, _ in pairs)
        change.writes[path] = text
        return change

    def standing_cost(self, target, context):
        return "none"


MEMBER = LanguageKind
