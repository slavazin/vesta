"""The `consolidate` step: pairs of records in force whose titles and opening lines share half or
more of their words, each pair in full."""
from __future__ import annotations

from model.abstractions import DECIDED
from session import passes
from steps.base import NONE, TextStep, record_in_full
from stores import similar


class ConsolidateStep(TextStep):
    id = "consolidate"
    title = "Consolidate"

    def data(self, context):
        found = context.walk.session
        number, opened, _ = passes.last(context)
        since = opened[:10] if number is not None else ""
        lines, count, printed = [], 0, set()
        for store in context.stores.recalled():
            for first, second in similar.pairs(store):
                count += 1
                new = [record.label for record in (first, second) if since and str(store.type.life(record, DECIDED) or "") >= since]
                lines.extend(["" if lines else None, "Pair %d: %s and %s%s" % (
                    count, first.label, second.label, " (added since the last pass: %s)" % ", ".join(new) if new else "",
                )])
                for record in (first, second):
                    lines.extend(record_in_full(context, record) if record.uid not in printed else ["%s is printed in full above." % record.label])
                    printed.add(record.uid)
        if found.pairs != count:
            found.data["pairs"] = count
            passes.save(context.tree, found)
        return [line for line in lines if line is not None]


MEMBER = ConsolidateStep
