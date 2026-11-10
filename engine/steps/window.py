"""The `window` step: everything a learn pass reads. The notes of its window that are still open,
each in full; then what earlier passes read and what the owner turned down, for memory across passes."""
from __future__ import annotations

from session import observations, passes
from steps.base import NONE, TextStep
from stores import admissions


class WindowStep(TextStep):
    id = "window"
    title = "Window"

    def data(self, context):
        found = context.walk.session
        open_ones = passes.still_open(context, found)
        count, done = len(found.window), len(found.window) - len(open_ones)
        lines = ["%s reads %d note%s, from %d session%s." % (
            found.id, count, "" if count == 1 else "s", passes.sessions(context, found), "" if passes.sessions(context, found) == 1 else "s",
        )]
        lost = count - len(passes.records(context, found))
        if done - lost:
            lines.append("Already dealt with in this pass: %d. Still open: %d." % (done - lost, len(open_ones)))
        if lost:
            lines.append("No longer in the store, or not readable: %d. `check` names a file that does not read; this pass leaves those as they are." % lost)
        lines.extend(["", "The notes still open, each in full:"])
        for store, record in open_ones:
            lines.append("")
            lines.extend(observations.form(store, record))
        if not open_ones:
            lines.append(NONE)
        fired = passes.firing(context, found)
        lines.extend(["", "Notes whose `%s` fires now: %s" % (observations.RECHECK, ", ".join(record.label for record in fired) or NONE)])
        lines.extend(["", "Read by the last three passes and archived with nothing done (id, where it came from, title):"])
        lines.extend([
            "- %s · %s · %s" % (record.label, record.get(observations.VIA) or "not stated", store.title(record) or "(no title)")
            for store, record in passes.read_before(context, found)
        ] or [NONE])
        lines.extend(["", "Proposals the owner turned down (`%s`):" % admissions.PATH])
        lines.extend(admissions.rejections(context.tree) or [NONE])
        number, since = passes.since_review(context)
        lines.append("")
        if number is None:
            lines.append("Trigger review: never run; passes sealed so far: %d." % since)
        else:
            lines.append("Trigger review: last run in %s; passes sealed since: %d." % (passes.NAME % number, since))
        return lines


MEMBER = WindowStep
