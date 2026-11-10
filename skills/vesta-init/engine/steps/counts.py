"""The `counts` step: what the consultation log and the window say, one figure at a time. The
figures point at where to look; the step adds none together and compares none."""
from __future__ import annotations

from kernel import ids
from session import log, observations, passes, state
from steps.base import NONE, TextStep

BY = (state.SCOPE, state.INDEX, state.TRIGGER, state.SWEEP)
MARKS = state.MARKS + (log.UNMARKED, log.UNCLOSED)
MISSED = "missed-by"


def _figures(names, counted):
    return ", ".join("%s %d" % (name, counted.get(name, 0)) for name in names)


class CountsStep(TextStep):
    id = "counts"
    title = "Counts"

    def data(self, context):
        found = context.walk.session
        number, opened, _ = passes.last(context)
        since = opened if number is not None else ""
        lines = ["From the sessions that ended %s:" % ("after %s opened, at %s" % (passes.NAME % number, opened) if since else "up to now; no earlier pass is on record"), ""]
        by, marks, empty = {}, {}, set()
        for entry in log.read(context.tree):
            if str(entry.get("at", "")) <= since:
                continue
            uid = ids.parse_ref(str(entry.get("record", "")))[1]
            if not uid:
                if entry.get("mark") != log.UNCLOSED:
                    empty.add(entry.get("session"))
                continue
            by.setdefault(uid, {}).setdefault(entry.get("by"), set()).add(entry.get("session"))
            marks.setdefault(uid, {}).setdefault(entry.get("mark"), set()).add(entry.get("session"))
        quiet = []
        lines.append("For each decision in force, the sessions that read it and what each said came of it:")
        listed = 0
        for store in context.stores.recalled():
            for record in store.list():
                if not store.type.is_accepted(record):
                    continue
                listed += 1
                if record.uid not in by:
                    quiet.append(record.label)
                    continue
                lines.append("- %s · read by: %s · marked: %s" % (
                    record.label,
                    _figures(BY, dict((name, len(sessions)) for name, sessions in by[record.uid].items())),
                    _figures(MARKS, dict((name, len(sessions)) for name, sessions in marks[record.uid].items())),
                ))
        if not listed:
            lines.append(NONE)
        if quiet:
            lines.append("- read by no session: %s" % ", ".join(quiet))
        lines.append("- sessions that read no decision: %d" % len(empty))
        window = passes.records(context, found)
        for field, said in ((observations.VIA, "where it came from"), (MISSED, "what should have caught it")):
            lines.extend(["", "Notes of this pass by `%s`, %s:" % (field, said)])
            counted = {}
            for _, record in window:
                value = " ".join(str(record.get(field) or "").split())
                if value:
                    counted[value] = counted.get(value, 0) + 1
            lines.extend(["- %s: %d" % (value, counted[value]) for value in sorted(counted)] or [NONE])
        return lines


MEMBER = CountsStep
