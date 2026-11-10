"""`load <id>… [--by index|trigger]`: print records in full and add each to the session's loaded list."""
from __future__ import annotations

from cli import args, sessions
from cli.commands import show
from kernel.errors import Refusal, UsageError
from session import state


def run(context, arguments):
    names, options = args.split(arguments, options=("--by", sessions.OPTION), takes=True)
    by = options.get("--by", state.INDEX)
    if by not in state.LOADERS:
        raise UsageError("`--by` is one of %s: how the record was found" % ", ".join(state.LOADERS))
    if not names:
        raise UsageError("`load` takes one or more record ids, as `load D-004`")
    found = [show.resolve(context, name) for name in names]
    session = sessions.current(context, options)
    if session.status != state.OPEN:
        raise Refusal("%s is %s; a record is loaded into an open session. `show <id>` prints one without a session." % (session.id, session.status), state.RULE)
    added = []
    for store, record in found:
        if session.load(record, by):
            added.append(record.label)
        show.print_record(context, record)
    state.save(context.tree, session)
    already = [record.label for _, record in found if record.label not in added]
    context.write("Loaded into %s: %s." % (session.id, ", ".join(added) or "nothing new"))
    if already:
        context.write("Already loaded, and left as first found: %s." % ", ".join(already))
    return 0
