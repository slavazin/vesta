"""The `draft` step: where the form of a proposal and the writing rules are, and the kinds this project allows."""
from __future__ import annotations

from steps.mint import LANGUAGE
from session import pending
from steps.base import NONE, TextStep
from stores.schema import FILE as SCHEMA_FILE


class DraftStep(TextStep):
    id = "draft"
    title = "Draft"

    def data(self, context):
        lines = ["- how a proposal is written: %s" % (", ".join("`%s/%s`" % (store.path, SCHEMA_FILE) for store in pending.stores_of(context)) or NONE)]
        lines.append("- the writing rules: `%s`" % LANGUAGE)
        lines.append("- the kinds of change this project allows: %s" % (", ".join("`%s`" % kind for kind in context.config.kinds) or NONE))
        lines.append("- the source to give each proposal of this pass: `%s`" % context.walk.session.id)
        return lines

    def words(self, context):
        return {"pass": context.walk.session.id}


MEMBER = DraftStep
