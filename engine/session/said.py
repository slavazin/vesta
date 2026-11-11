"""The `conversation` capture source: what the owner said while a task was worked on, read back from
the conversation as the harness keeps it, when the task is reviewed.

What it reads is recorded as read, by the session that reviews it, so that `/vesta-backfill` does not
read the same words a second time.
"""
from __future__ import annotations

from kernel.errors import Refusal, UsageError
from model.abstractions import CaptureSource
from session import asides, harness, history, jotting, state


def floor(context, session, mark):
    """The moment from which the owner's words belong to this session: the last thing read back from
    the conversation before, else the session's opening, else the conversation's start."""
    done = [entry["until"] for entry in history.read(context.tree)
            if entry["conversation"] == mark and entry["session"] != session.id and history.counts(context.tree, entry)]
    if done:
        return max(done)
    return "" if session.late else session.opened


def read_back(context, session):
    """(the history, the conversation, every piece this session holds of it, the moment they start at).
    Marks what is new as read by this session. Raises UsageError or Refusal where it cannot be read."""
    found = harness.current(context)
    name = state.conversation_of(session) or (found.conversation() if found is not None else "")
    if found is None or not found.history or not name:
        raise UsageError("%s did not say which conversation this is" % (found.name if found is not None else "the harness"))
    kept = history.member(context, found.history)
    conversation = history.find(kept, name)
    turns = history.said(kept, conversation)
    mark = history.key(kept, conversation)
    with history.lock(context.tree) as held:
        if not held:
            raise UsageError("another command is reading a conversation back at this moment; run this command again")
        readings = history.read(context.tree)
        since = floor(context, session, mark)
        own = set(history.held(readings, session.id, mark))
        taken = history.marks_read(context.tree, [entry for entry in readings if entry["session"] != session.id])
        fresh = [turn for turn in history.mine(turns)
                 if turn.mark not in own and turn.mark not in taken and (not turn.at or turn.at[:19] >= since[:19])]
        if fresh and session.status == state.OPEN:
            until = max([turn.at for turn in fresh if turn.at] or [conversation.dated])
            history.record(context.tree, readings, mark, session, context.clock.today(), [turn.mark for turn in fresh], until)
            own.update(turn.mark for turn in fresh)
    return kept, conversation, history.pieces(turns, own), since


def _flat(text):
    return " ".join(text.split())[:asides.WORDS]


def _covered(piece, done):
    """Say whether a copy that reported was started for the words a piece is part of."""
    words = _flat(piece.turn.text)
    return any(words == other or (len(other) >= 20 and (other in words or words in other)) for other in done)


class SaidCapture(CaptureSource):
    id = jotting.CAPTURE

    def steers(self, session):
        return []

    def lines(self, session, context):
        mode = jotting.in_effect(context)
        if mode == jotting.HERE:
            return []
        try:
            kept, conversation, pieces, since = read_back(context, session)
        except (UsageError, Refusal) as error:
            return ["What the owner said could not be read back from the conversation: %s. Go through the conversation as you hold it." % getattr(error, "message", error)]
        lines = []
        if mode == jotting.ASIDE:
            try:
                copies = asides.of(context.tree, conversation.ref, since)
            except UsageError as error:
                copies, lines = [], [str(error)]
            # A thing the owner said is dealt with where a copy was started for those words and reported back.
            done = [_flat(entry["words"]) for entry in copies if entry["answer"] in (asides.NOTED, asides.NOTHING)]
            left = [piece for piece in pieces if not _covered(piece, done)]
            noted = len([entry for entry in copies if entry["answer"] == asides.NOTED])
            said = len(set(piece.turn.mark for piece in pieces))
            if not left:
                return lines + ["Noted aside: the owner said %d thing%s in this task, a copy of the conversation was started for each, and each reported back. "
                                "%d noted a correction, which is among the corrections above; the rest found none."
                                % (said, "" if said == 1 else "s", noted)] if pieces else lines + ["The owner said nothing in this task after it began."]
            if not copies:
                lines.append("No copy of the conversation was started in this task: the entry that starts one is not in place, or was not when the owner "
                             "spoke. `setting jotting aside` prints it. What the owner said is read back here instead.")
            else:
                lines.append("A copy of the conversation was started %d time%s, and %d reported back. Of the %d thing%s the owner said, %d had no copy that "
                             "reported, and %s read back here; a correction above that a copy noted is not repeated."
                             % (len(copies), "" if len(copies) == 1 else "s", len(done), said, "" if said == 1 else "s",
                                len(set(piece.turn.mark for piece in left)), "is" if len(left) == 1 else "are"))
            pieces = left
        lines.append("What the owner said%s, read from the conversation as %s keeps it (%s): %d piece%s."
                     % (" since %s" % since if since else "", kept.name, conversation.path.replace("\\", "/"), len(pieces), "" if len(pieces) == 1 else "s"))
        if kept.harness:
            lines.append("Left out: %d thing%s the harness wrote in the owner's place." % (kept.harness, "" if kept.harness == 1 else "s"))
        if kept.unread:
            lines.append("Not read: %d line%s of the file that could not be read." % (kept.unread, "" if kept.unread == 1 else "s"))
        if not pieces:
            return lines
        lines.append("")
        shown, following = history.lines(pieces, 1)
        lines.extend(shown)
        if following is not None:
            lines.append("This printing stops at piece %d. The rest is printed with `history turns %s %s %s %s --at %d`, then the number its last line names, until it says the end."
                         % (following - 1, kept.id, history.quoted(conversation.ref), history.SESSION_OPTION, session.id, following))
        return lines


MEMBER = SaidCapture
