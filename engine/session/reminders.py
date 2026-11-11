"""The reminders a start sheet may carry: that a learn pass is due. Each is off where the
configuration turns it off, and each condition is read alone."""
from __future__ import annotations

from kernel.errors import UsageError
from session import history, observations, passes, state


def due(context):
    """One line for each reminder whose condition is met; none for one that is off."""
    return _learn(context) + _unreviewed(context)


def unreviewed(context):
    """The tasks' sessions that ended without a review, abandoned with nothing noted from them, and
    later than the last thing said in any conversation read back. A conversation read back from long
    ago therefore quiets nothing. Raises UsageError where the record does not read."""
    since = max([entry["until"] for entry in history.read(context.tree) if history.counts(context.tree, entry)] or [""])
    return [session for session in state.every(context.tree)
            if session.origin is None and session.status == state.ABANDONED and not session.minted and session.data.get("ended", "") > since]


def _unreviewed(context):
    wanted = context.config.remind_unreviewed
    if wanted <= 0:
        return []
    try:
        count = len(unreviewed(context))
    except UsageError:
        return []  # `doctor` names the file that does not read; a start sheet goes on without this line
    if count < wanted:
        return []
    return ["%d task%s ended without a review, and the reminder is set at %d (`reminders.unreviewed.sessions`): "
            "`/vesta-backfill` reads %s back for what the owner corrected in %s, where it can find the conversation or is given it. "
            "The owner can ask for this reminder to be turned off."
            % (count, "" if count == 1 else "s", wanted, "its conversation" if count == 1 else "their conversations", "it" if count == 1 else "them")]


def _learn(context):
    config = context.config
    if not config.remind_learn:
        return []
    lines = []
    if config.remind_open_observations > 0:
        count = observations.open_count(context)
        if count >= config.remind_open_observations:
            lines.append(
                "learn pass due: %d notes are open, and the reminder is set at %d (`reminders.learn.open-observations`)."
                % (count, config.remind_open_observations)
            )
    if config.remind_sessions_since_pass > 0:
        count = passes.closed_since(context)
        if count >= config.remind_sessions_since_pass:
            lines.append(
                "learn pass due: %d session%s closed since the last learn pass, and the reminder is set at %d (`reminders.learn.sessions-since-pass`)."
                % (count, " has" if count == 1 else "s have", config.remind_sessions_since_pass)
            )
    return lines
