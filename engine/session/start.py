"""How the start walk opens: a new session, a further task in the open one, or a new one in place of
one an earlier conversation left open."""
from __future__ import annotations

from kernel.errors import Refusal, UsageError
from model.abstractions import Opening
from session import log, state

CASES = ("continue", "new", "parallel")


def _task(session):
    """Refuse a session that reads back an earlier conversation: it is no task's, and this walk neither goes on in it nor ends it."""
    if session.origin is not None:
        raise Refusal(
            "%s reads back an earlier conversation, and this walk belongs to a task's session. `walk backfill --session %s` prints "
            "its sheet; `session abandon %s` leaves it. Nothing was changed." % (session.id, session.id, session.id),
            "vesta/INTERNALS.md, Earlier conversations",
        )
    return session


class StartOpening(Opening):
    flags = tuple("--" + case for case in CASES)

    def open(self, context, options):
        chosen = [case for case in CASES if options.get(case)]
        if len(chosen) > 1:
            raise UsageError("`--%s` and `--%s` name two different cases; give one" % (chosen[0], chosen[1]))
        tree, ask = context.tree, options.get("ask", "")
        found = state.open_ones(tree)
        if options.get("continue"):
            session = _task(state.current(tree, options.get("session")))
            if session.status != state.OPEN:
                raise Refusal("%s is %s; `--continue` adds a task to a session that is open." % (session.id, session.status), state.RULE)
            if ask:
                session.asks.append(ask)
                state.save(tree, session)
            return session, ["Continuing session %s%s." % (session.id, "; the task was added to it" if ask else "")]
        said = []
        if options.get("new"):
            if options.get("session"):
                left = [_task(state.named(tree, options["session"]))]
                if left[0].status != state.OPEN:
                    raise Refusal("%s is already %s; `--new --session` names an open session to leave." % (left[0].id, left[0].status), state.RULE)
            elif len(found) > 1:
                left = [state.current(tree)]
            else:
                left = found
            for session in left:
                lines = log.end(context, session, state.ABANDONED)
                said.append("Session %s was left unfinished: it is now marked abandoned, and %d line%s went to the log as `unclosed`." % (
                    session.id, len(lines), "" if len(lines) == 1 else "s"))
        elif found and not options.get("parallel"):
            raise Refusal(
                "a session is already open:\n%s\nSay which case holds.\n"
                "- This conversation opened it and has moved to a further task: run `walk start --continue` with the new task.\n"
                "- It belongs to an earlier conversation: tell the owner, run `walk close --short --session %s` and carry that sheet out "
                "from what it prints, then run `walk start --new` with the task.\n"
                "- A second agent is working in this checkout at the same time: run `walk start --parallel`; every later command then takes `--session <id>`."
                % ("\n".join("- " + session.one_line() for session in found), found[0].id),
                state.RULE,
            )
        session = state.create(context, ask)
        said.append("Opened session %s." % session.id)
        said.extend(state.base_lines(session))
        if options.get("parallel") and found:
            said.append("%d other session%s open, so every later command takes `--session %s`." % (
                len(found), " is" if len(found) == 1 else "s are", session.id))
        return session, said


MEMBER = StartOpening
