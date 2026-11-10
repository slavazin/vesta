"""What the commands share about sessions: which one a command means, and what the engine wrote in it."""
from __future__ import annotations

from kernel import tree as trees
from session import late, state

OPTION = "--session"


def current(context, options):
    """The session a command means; it becomes the context's session."""
    context.session = state.current(context.tree, options.get(OPTION))
    return context.session


def current_or_late(context, options):
    """As `current`, opening a late session where none is open. Returns (session, opened just now)."""
    context.session, opened = late.open_or_late(context, options.get(OPTION))
    return context.session, opened


def note_written(context):
    """Add the paths this command wrote to the list of every open session, and of the session the
    command ran in, so that no session reports the engine's writes as its own changes."""
    written = [path for path in getattr(context.tree, "written", ()) if not path.startswith(trees.STATE)]
    if not written:
        return
    named = [context.session.id] if isinstance(context.session, state.Session) else []
    for name in dict.fromkeys(named + [session.id for session in state.open_ones(context.tree)]):
        fresh = state.read(context.tree, name)
        if fresh is None:
            continue
        added = [path for path in dict.fromkeys(written) if path not in fresh.written]
        if added:
            fresh.written.extend(added)
            state.save(context.tree, fresh)
