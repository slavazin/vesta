"""`session show | close | abandon <id>`: read a session, or end one."""
from __future__ import annotations

from cli import args, manifest, sessions
from kernel.errors import Refusal, UsageError
from session import log, state
from steps import sheet

ACTS = ("show", "close", "abandon")
BUNDLE = "bundle"


def _count(lines):
    loaded = [line for line in lines if line["record"]]
    if not loaded:
        return "one line saying that no record was loaded"
    return "%d line%s, one for each loaded record" % (len(loaded), "" if len(loaded) == 1 else "s")


def run(context, arguments):
    words, options = args.split(arguments, options=(sessions.OPTION,), takes=True)
    if not words or words[0] not in ACTS:
        raise UsageError("`session` takes one of: %s" % ", ".join(ACTS))
    act, rest = words[0], words[1:]
    if act == "abandon":
        if len(rest) != 1:
            raise UsageError("`session abandon` takes the id of the session to leave, as `session abandon S-20260314-1c0e`")
        session = state.named(context.tree, rest[0])
    elif rest:
        raise UsageError("`session %s` takes no `%s`; name a session with `--session <id>`" % (act, rest[0]))
    else:
        session = sessions.current(context, options)
    context.session = session
    if act == "show":
        step = manifest.member("steps", BUNDLE)()
        context.walk = sheet.Walk(None, session)
        section = step.render(context)
        context.write("# Session %s" % session.id)
        context.write()
        for line in section.data:
            context.write(line)
        return 0
    if session.status != state.OPEN:
        raise Refusal("%s is already %s. Nothing was changed." % (session.id, session.status), state.RULE)
    lines = log.end(context, session, state.CLOSED if act == "close" else state.ABANDONED)
    if session.origin is not None and not lines:
        context.write("%s %s. It read back an earlier conversation and loaded no record, so the log took no line."
                      % ("Closed" if act == "close" else "Marked abandoned:", session.id))
        return 0
    if act == "close":
        unmarked = [line["record"].split("@")[0] for line in lines if line["mark"] == log.UNMARKED]
        context.write("Closed %s. The log took %s." % (session.id, _count(lines)))
        if unmarked:
            context.write("Logged as `unmarked`, since no mark was set: %s." % ", ".join(unmarked))
    else:
        context.write("%s is marked abandoned. The log took %s, marked `unclosed`. Its jots were not turned into notes." % (session.id, _count(lines)))
    return 0
