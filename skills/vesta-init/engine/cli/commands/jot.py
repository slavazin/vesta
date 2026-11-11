"""`jot [--steer] [--anchor <a>] <text or ->`: note something in the session, in seconds."""
from __future__ import annotations

from cli import args, sessions
from kernel.errors import Refusal, UsageError
from session import state


def run(context, arguments):
    words, options = args.split(arguments, flags=("--steer",), options=("--anchor", sessions.OPTION), takes=True)
    if len(words) != 1:
        raise UsageError("`jot` takes one text, or `-` to read it from standard input, as `jot --steer -`")
    text = args.text(words[0], context.stdin)
    if not text.strip():
        raise UsageError("the jot is empty; nothing was noted")
    session, opened = sessions.current_or_late(context, options)
    sessions.ordinary(session, "a jot")
    if session.status != state.OPEN:
        raise Refusal("%s is %s; a jot goes into an open session. Run `jot` without `--session`, and one is opened to hold it." % (session.id, session.status), state.RULE)
    at, steer, anchor = context.clock.timestamp(), "--steer" in options, options.get("--anchor", "")
    session = context.session = state.update(context.tree, session, lambda fresh: fresh.jot(at, text, steer, anchor))
    if opened:
        context.write("No session was open, so %s was opened late to hold this jot." % session.id)
    context.write("Noted in %s (%d so far%s)." % (session.id, len(session.jots), ", as a correction from the owner" if "--steer" in options else ""))
    return 0
