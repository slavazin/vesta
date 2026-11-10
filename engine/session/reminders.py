"""The reminders a start sheet may carry: that a learn pass is due. Each is off where the
configuration turns it off, and each condition is read alone."""
from __future__ import annotations

from session import observations, passes


def due(context):
    """One line for each condition of the learn reminder that is met; none where the reminder is off."""
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
