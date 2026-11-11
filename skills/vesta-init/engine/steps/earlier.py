"""The `earlier` step: what the owner said in a conversation held before now, a printing at a time,
then every record in force by its label and the line saying when to open it."""
from __future__ import annotations

from kernel.errors import Refusal, UsageError
from session import history, observations
from steps.base import TextStep
from steps.steers import in_force

KEPT = {
    "": "every time the owner corrected the work, redirected it, chose between alternatives the agent put, or stated how work is to be done in this project",
    "corrections": "every time the owner said that something done was wrong. The owner asked for corrections only: a new direction, a choice and a stated preference are left out",
}


def of_session(context, session):
    """(the history, the conversation, the pieces a session was opened to read). Raises Refusal or
    UsageError where the conversation can no longer be read."""
    origin = session.origin or {}
    found = history.member(context, origin.get("history"), origin.get("in") or "")
    conversation = history.find(found, origin.get("conversation"))
    marks = origin.get("marks")
    return found, conversation, history.pieces(history.said(found, conversation), set(marks) if isinstance(marks, list) else None)


class EarlierStep(TextStep):
    id = "earlier"
    title = "What was said"
    needs = "conversation"

    def data(self, context):
        session = context.walk.session
        self.dated, self.told = "", True
        if session.origin is None:
            return ["This session was not opened to read back an earlier conversation, so there is nothing to print."]
        try:
            found, conversation, pieces = of_session(context, session)
        except (Refusal, UsageError) as error:
            return ["The conversation this session was opened for can no longer be read: %s" % error]
        self.dated = history.dated(conversation, pieces)
        self.told = any(piece.turn.who for piece in pieces)
        lines = [
            "Read from: %s (%s)." % (found.name, conversation.path.replace("\\", "/")),
            "%s: %s." % (found.day_word if self.dated == conversation.dated else "Held on", self.dated or "a day not known"),
            "To read: %d piece%s %s. A message longer than %d characters is printed as several pieces."
            % (len(pieces), "" if len(pieces) == 1 else "s", "by the owner" if self.told else "of text, the owner's words and the agent's together", history.CUT),
        ]
        if found.harness:
            lines.append("Left out: %d thing%s the harness wrote in the owner's place." % (found.harness, "" if found.harness == 1 else "s"))
        if found.unread:
            lines.append("Not read: %d line%s of the file that could not be read." % (found.unread, "" if found.unread == 1 else "s"))
        lines.append("")
        shown, following = history.lines(pieces, 1)
        lines.extend(shown)
        if following is not None:
            option = " %s %s" % (history.PATH_OPTION, history.quoted(session.origin["in"])) if session.origin.get("in") else ""
            lines.append(
                "This printing stops at piece %d. The rest is printed with `history turns %s %s%s %s %s --at %d`, then the number its last line names, until it says the end."
                % (following - 1, found.id, history.quoted(conversation.ref), option, history.SESSION_OPTION, session.id, following)
            )
            lines.append("")
        listed = in_force(context)
        if sum(len(line) + 1 for line in listed) > history.IN_FORCE:
            listed = [listed[0], "There are %d, too many to list here. `index` prints each with the line saying when to open it; run it before naming one." % (len(listed) - 1)]
        return lines + listed

    def words(self, context):
        only = (context.walk.session.origin or {}).get("only") or ""
        return {
            "anchor": ("`owner, ` followed by the day its piece shows, or `owner, %s` where the piece shows none" % (self.dated or "day not known"))
            if self.told else "`owner, in saved text` followed by the file's name: the text shows no day, and the day the file was last changed is not the day it was said",
            "kept": KEPT.get(only, KEPT[""]),
            # Said only where it is so: a store whose records have no such field gets no such line.
            "recorded": " The engine records that the observation was read back; don't say so in its body."
            if any(observations.sourced(store) for store in observations.stores_of(context)) else "",
            "speaker": "" if self.told else " This text does not say who spoke: tell the owner's words from the agent's by what they say, and leave out what cannot be told.",
        }


MEMBER = EarlierStep
