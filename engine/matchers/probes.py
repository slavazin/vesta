"""Probes: a condition the engine evaluates by reading the project. A probe never runs a command.

A probe is written `<keyword> <the rest>`. The keyword names a matcher the engine holds; the matcher
reads the rest.
"""
from __future__ import annotations

from model.abstractions import MatchError

TABLE = "probes"
FIRED, UNFIRED, ERROR, NONE = "fired", "unfired", "error", "no probe"


class State(object):
    """What evaluating a probe found: `fired`, `unfired`, `error` with the reason, or `no probe`."""

    def __init__(self, state, reason="", skipped=0):
        self.state = state
        self.reason = reason
        self.skipped = skipped

    def text(self):
        text = "%s: %s" % (self.state, self.reason) if self.reason else self.state
        if self.skipped:
            text += " (%d file%s skipped as too large, not text, or outside the project)" % (self.skipped, "" if self.skipped == 1 else "s")
        return text


def parse(text, context):
    """(the matcher, what it is to read) for a probe's text. Raises MatchError where it does not read."""
    words = text.strip().split(None, 1)
    keyword = words[0] if words else ""
    known = context.known.get(TABLE, ())
    if keyword not in known:
        raise MatchError("a probe opens with one of %s; this one opens with `%s`" % (", ".join("`%s`" % name for name in known), keyword))
    matcher = context.member(TABLE, keyword)()
    subject = words[1] if len(words) > 1 else ""
    matcher.parse(subject)
    return matcher, subject


def evaluate(text, context):
    """The State of a probe's text. An empty text is `no probe`; one that cannot be evaluated is an error."""
    if not isinstance(text, str) or not text.strip():
        return State(NONE)
    try:
        matcher, subject = parse(text, context)
        fired = matcher.match(subject, context)
    except MatchError as error:
        return State(ERROR, str(error))
    return State(FIRED if fired else UNFIRED, skipped=matcher.skipped)
