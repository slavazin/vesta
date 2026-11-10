"""How every walk but the start walk opens: in the open session, or in a late one where none is open."""
from __future__ import annotations

from kernel.errors import Refusal
from model.abstractions import Opening
from session import state


def open_or_late(context, name=None, ask=""):
    """(the session a command means, whether it was opened just now). With none open and none named,
    a late session is opened: one that begins after the work it belongs to."""
    if name or state.open_ones(context.tree):
        return state.current(context.tree, name), False
    return state.create(context, ask, late=True), True


class LateOpening(Opening):
    def open(self, context, options):
        name, start = options.get("session"), options.get("from")
        if start and not name and not state.open_ones(context.tree):
            ended = [session for session in state.every(context.tree) if session.status != state.OPEN]
            last = max(ended, key=lambda session: session.data.get("ended", "")) if ended else None
            raise Refusal(
                "`--from %s` prints a later part of a walk, and no session is open for it to belong to. Name the session the first "
                "part ran in%s." % (start, ", as `--session %s`, the one that ended last" % last.id if last else ""),
                state.RULE,
            )
        session, opened = open_or_late(context, name, options.get("ask", ""))
        if opened:
            return session, [
                "No session was open, so %s was opened late: it holds no task, no loaded record and no jot from the work already done." % session.id
            ] + state.base_lines(session)
        said = []
        if session.status != state.OPEN:
            said.append("This session is %s: the sheet shows what it recorded, and it takes no further mark, jot or observation." % session.status)
        else:
            said.append("It was already open: opened %s." % session.opened)
        if options.get("ask"):
            said.append("The text given with `--ask` was not recorded: the session already holds its task.")
        return session, said

    def paths(self, context, session, given):
        """A walk that follows the work is matched against what the work changed."""
        return list(given) or state.changed(context, session)[0]


MEMBER = LateOpening
