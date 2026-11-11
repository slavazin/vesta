"""`mark <id>=<mark>…`: say what came of each loaded record."""
from __future__ import annotations

from cli import args, sessions
from cli.commands import show
from kernel.errors import Refusal, UsageError
from session import state

RULE = "vesta/INTERNALS.md, Sessions"


def run(context, arguments):
    pairs, options = args.split(arguments, options=(sessions.OPTION,), takes=True)
    if not pairs:
        raise UsageError("`mark` takes pairs, as `mark D-004=applied D-009=not-applicable`; the marks are: %s" % ", ".join(state.MARKS))
    wanted = []
    for pair in pairs:
        name, sign, mark = pair.partition("=")
        if not sign or mark not in state.MARKS:
            raise UsageError("`%s` is not `<id>=<mark>`; the marks are: %s" % (pair, ", ".join(state.MARKS)))
        wanted.append((show.resolve(context, name)[1], mark))
    session = sessions.ordinary(sessions.current(context, options), "a mark")
    if session.status != state.OPEN:
        raise Refusal(
            "%s is %s and its marks are already in the log, so a mark set now would never reach it. Nothing was marked." % (session.id, session.status),
            RULE,
        )
    for record, mark in wanted:
        entry = session.entry(record)
        if entry is not None and mark == state.SHOULD_HAVE_LOADED and entry.get("by") != state.SWEEP:
            raise Refusal(
                "%s was loaded in %s (by %s), so it cannot be marked `%s`: that mark is for a record the session never read. "
                "Mark it `%s` or `%s`. Nothing was marked."
                % (record.label, session.id, entry.get("by"), mark, state.APPLIED, state.NOT_APPLICABLE),
                RULE,
            )
    for record, mark in wanted:
        if session.entry(record) is None and mark != state.SHOULD_HAVE_LOADED:
            raise Refusal(
                "%s was not loaded in %s, so it cannot be marked `%s`. Run `load %s` first where the work used it; "
                "mark it `%s` where it governed the work and was not read. Nothing was marked."
                % (record.label, session.id, mark, record.label, state.SHOULD_HAVE_LOADED),
                RULE,
            )
    for record, mark in wanted:
        if session.entry(record) is None:
            session.load(record, state.SWEEP)
        session.entry(record)["mark"] = mark
    state.save(context.tree, session)
    context.write("Marked in %s: %s." % (session.id, ", ".join("%s %s" % (record.label, mark) for record, mark in wanted)))
    left = [entry.get("record", "").split("@")[0] for entry in session.loaded if not entry.get("mark")]
    if left:
        context.write("Loaded and not marked yet: %s." % ", ".join(left))
    return 0
