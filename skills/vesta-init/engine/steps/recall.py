"""The `recall` step: for every store whose index joins the start walk, the records the given paths
reach, in full and loaded; then one index block for every other record in force."""
from __future__ import annotations

from matchers import index, scope
from session import state
from steps.base import NONE, TextStep, record_in_full


def _count(number, word):
    return "%d %s%s" % (number, word, "" if number == 1 else "s")


class RecallStep(TextStep):
    id = "recall"
    title = "Recall"

    def data(self, context):
        walk = context.walk
        session = walk.session
        lines = []
        changed = False
        stores = context.stores.recalled()
        for store in stores:
            if lines:
                lines.append("")
            lines.extend(["### %s" % store.name, ""])
            reached = scope.matching(store, walk.paths) if walk.paths else []
            for record in reached:
                changed = session.load(record, state.SCOPE) or changed
            reached_paths = set(record.path for record in reached)
            others = [record for record in store.list() if store.type.is_accepted(record) and record.path not in reached_paths]
            if not reached and not others:
                lines.append(NONE)
            if reached:
                lines.extend(["Reached by the paths given, loaded, and printed in full:", ""])
                for record in reached:
                    lines.extend(record_in_full(context, record) + [""])
            if others:
                lines.extend(["Index of the %s:" % ("other records" if reached else "records"), "", "```"])
                for position, record in enumerate(others):
                    if position:
                        lines.append("")
                    lines.extend(index.block(store, record))
                lines.extend(["```", ""])
            total = len(reached) + len(others)
            if total:
                lines.append("Counts: %s in force; %s loaded in full; %s." % (_count(total, "record"), len(reached), _count(len(others), "index block")))
            if total >= context.config.long_index_at:
                lines.append("The index is long (%s). A learn pass could look for records to merge." % _count(total, "record"))
            unread = store.unread()
            if unread:
                lines.extend(["", "**Not everything is listed.** These do not read, and `check` says why: %s." % ", ".join(unread)])
        lost = sorted(name for name in context.stores.unreadable if context.config.stores[name].recall == "index")
        if lost:
            lines.extend(["", "**Not everything is listed.** The store %s cannot be read, and `check` says why." % ", ".join("`%s`" % name for name in lost)])
        if changed:
            state.save(context.tree, session)
        return lines


MEMBER = RecallStep
