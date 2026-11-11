"""Conversations held before now: which place they are read from, what of them has been read back,
and how one is printed in pieces a reader can take in.

What was read is remembered by what was said, not by the file: each thing the owner said has a mark
of its own, so a conversation that was added to is offered again for what is new, and one that was
carried on in a second file is not read twice.
"""
from __future__ import annotations

import hashlib
import json
import os
import re

from kernel.errors import Refusal, UsageError
from model.abstractions import HistoryError, Turn
from session import state

TABLE = "histories"
PATH = "vesta/.state/history.json"
LOCK = "vesta/.state/history.lock"
RULE = "vesta/INTERNALS.md, Earlier conversations"
READINGS = "readings"
# A piece is at most CUT characters; one printing holds about BUDGET characters, whatever the pieces are.
CUT, BEFORE, BUDGET = 1200, 240, 12000
PATH_OPTION, SESSION_OPTION = "--in", "--session"
DAY = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}(T|\Z)")
NAME = re.compile(r"[^-\s][^\n]*\Z")
PLAIN = re.compile(r"[A-Za-z0-9_./:@+-]+\Z")
# The records in force are listed on a sheet up to this many characters; past it, a command lists them.
IN_FORCE = 6000


def sources(context):
    return list(context.known.get(TABLE, ()))


def member(context, name, given=""):
    """The history of that id over this project. Raises UsageError where there is none, where it
    reads a place the owner names and none was named, or where a place was named and it takes none."""
    known = sources(context)
    if name not in known:
        raise UsageError("`%s` is not a place this engine reads earlier conversations from; it reads: %s" % (name, ", ".join(known) or "none"))
    cls = context.member(TABLE, name)
    if cls.needs_path and not given:
        raise UsageError("`%s` reads a file or folder the owner names; give it as `%s <path>`" % (name, PATH_OPTION))
    if given and not cls.takes_path:
        raise UsageError("`%s` finds its own place and takes no `%s`" % (name, PATH_OPTION))
    return cls(context.root, given or "")


def listed(history):
    """(the conversations a command can name, oldest first; what was passed over, in words).
    Raises Refusal where the place cannot be read."""
    try:
        found = history.conversations()
    except HistoryError as error:
        raise Refusal("the earlier conversations of `%s` cannot be listed: %s. Nothing was read." % (history.id, error), RULE)
    usable = [conversation for conversation in found if NAME.match(conversation.ref)]
    passed = [history.left_out] if history.left_out else []
    if len(usable) != len(found):
        count = len(found) - len(usable)
        passed.append("%d file%s whose name opens with a dash or holds a line break, which no command can name" % (count, "" if count == 1 else "s"))
    return usable, ", ".join(passed)


def find(history, ref):
    found, _ = listed(history)
    for conversation in found:
        if conversation.ref == ref:
            return conversation
    names = ", ".join(conversation.ref for conversation in found[-10:]) or "none"
    option = " %s %s" % (PATH_OPTION, quoted(history.given)) if history.given else ""
    raise UsageError("`%s` is not a conversation of `%s`; `history list %s%s` prints them. The latest are: %s" % (ref, history.id, history.id, option, names))


def said(history, conversation):
    """What was said in a conversation. Raises Refusal where it cannot be read."""
    try:
        return history.turns(conversation)
    except HistoryError as error:
        raise Refusal("that conversation cannot be read: %s. Nothing was noted from it." % error, RULE)


def key(history, conversation):
    """What a conversation's file is remembered by."""
    place = os.path.normcase(os.path.realpath(conversation.path))
    return "%s:%s" % (history.id, hashlib.sha256(place.encode("utf-8", "surrogatepass")).hexdigest()[:16])


def _reads(entry):
    return (isinstance(entry, dict) and all(isinstance(entry.get(name), str) for name in ("session", "conversation", "at", "until"))
            and isinstance(entry.get("marks"), list) and all(isinstance(mark, str) for mark in entry["marks"]))


def read(tree):
    """Every reading recorded: [{conversation, session, at, marks}], oldest first."""
    if not tree.is_file(PATH):
        return []
    try:
        data = json.loads(tree.read(PATH))
    except (ValueError, UnicodeDecodeError, RecursionError):
        data = None
    found = data.get(READINGS) if isinstance(data, dict) else None
    if not isinstance(found, list) or not all(_reads(entry) for entry in found):
        raise UsageError(
            "%s does not read. It is the engine's working state and no record, so this one file may be deleted by hand; "
            "the conversations read back before will then be offered again. Then run the command again." % PATH
        )
    return found


def _session(tree, entry):
    """The session of a reading, or None where its file is gone or does not read."""
    try:
        return state.read(tree, entry["session"])
    except UsageError:
        return None


def counts(tree, entry):
    """Say whether a reading stands as done: its session closed, or gone, or left with notes written."""
    session = _session(tree, entry)
    if session is None or session.status == state.CLOSED:
        return True
    return session.status == state.ABANDONED and bool(session.minted)


def taken(tree, entry):
    """Say whether what a reading holds is spoken for: it is done, or a session is reading it now."""
    session = _session(tree, entry)
    return counts(tree, entry) or (session is not None and session.status == state.OPEN)


def marks_read(tree, readings):
    """The marks of everything read back or being read, in any conversation."""
    found = set()
    for entry in readings:
        if taken(tree, entry):
            found.update(entry["marks"])
    return found


def being_read(tree, readings, name):
    """The open session that is reading a conversation, or None."""
    for entry in readings:
        session = _session(tree, entry) if entry["conversation"] == name else None
        if session is not None and session.status == state.OPEN:
            return session
    return None


def last_read(tree, readings, name):
    """The latest reading of a conversation that stands as done, or None."""
    done = [entry for entry in readings if entry["conversation"] == name and counts(tree, entry)]
    return done[-1] if done else None


def forget(tree, name, marks):
    """Drop every reading of one conversation, and every reading that holds something said in it,
    so that it is offered again whole. Returns how many were dropped. Raises Refusal where a
    session is reading any of it now."""
    with lock(tree) as held:
        if not held:
            raise UsageError("another command is opening an earlier conversation at this moment; nothing was changed. Run this command again.")
        readings = read(tree)
        marks = set(marks)
        held = [entry for entry in readings if entry["conversation"] == name or marks.intersection(entry["marks"])]
        for entry in held:
            session = _session(tree, entry)
            if session is not None and session.status == state.OPEN:
                raise Refusal("%s is reading that conversation, or one that holds the same words, now. Close it, or leave it with "
                              "`session abandon %s`; nothing was changed." % (session.id, session.id), RULE)
        kept = [entry for entry in readings if entry not in held]
        if len(kept) != len(readings):
            tree.write(PATH, json.dumps({READINGS: kept}, indent=1, sort_keys=True) + "\n")
        return len(readings) - len(kept)


def lock(tree):
    """Hold this for the whole of deciding whether a conversation is read and opening a session for it."""
    return tree.lock(LOCK)


def record(tree, readings, name, session, at, marks, until):
    """`until` is the moment of the last thing read, or the day the file was last added to."""
    readings = list(readings) + [{"conversation": name, "session": session.id, "at": at, "marks": sorted(marks), "until": until}]
    tree.write(PATH, json.dumps({READINGS: readings}, indent=1, sort_keys=True) + "\n")


def mine(turns):
    """The things said that are read back: the owner's, or everything where the history cannot tell."""
    told, found, seen = any(turn.who for turn in turns), [], set()
    for turn in turns:
        # An entry a file holds twice is one thing said.
        if (turn.who == Turn.OWNER or not told) and turn.mark not in seen:
            seen.add(turn.mark)
            found.append(turn)
    return found


class Piece(object):
    """At most CUT characters of one thing said. `part` of `parts` where it was longer; `before` is
    what the agent said just before it, on its first part."""

    def __init__(self, turn, text, part, parts, before):
        self.turn, self.text, self.part, self.parts, self.before = turn, text, part, parts, before


def _split(text):
    """A text in runs of at most CUT characters, broken between lines where a line allows."""
    runs, held = [], ""
    for line in text.split("\n"):
        while len(line) > CUT:
            if held:
                runs.append(held)
                held = ""
            runs.append(line[:CUT])
            line = line[CUT:]
        if held and len(held) + 1 + len(line) > CUT:
            runs.append(held)
            held = line
        else:
            held = held + "\n" + line if held else line
    if held.strip() or not runs:
        runs.append(held)
    return runs


def pieces(turns, only=None):
    """The pieces to read, in order. `only` holds the marks to keep; None keeps every one."""
    wanted = set(turn.mark for turn in mine(turns))
    found, before = [], ""
    for turn in turns:
        if turn.mark in wanted and (turn.who != Turn.AGENT):
            wanted.discard(turn.mark)
            if only is None or turn.mark in only:
                runs = _split(turn.text.strip())
                found.extend(Piece(turn, run, number, len(runs), before if number == 1 else "") for number, run in enumerate(runs, 1))
            before = ""
        elif turn.who == Turn.AGENT:
            before = turn.text
    return found


def _flat(text):
    return " ".join(text.split())


def lines(found, start):
    """(the lines of the pieces from the one numbered `start`, the number the next printing starts at
    or None). A printing holds one piece at least, and stops before the piece that would take it past BUDGET."""
    shown, size, number = [], 0, start
    while number <= len(found):
        piece = found[number - 1]
        block = ["### %d of %d%s%s" % (
            number, len(found), " · %s" % piece.turn.at if piece.turn.at else "",
            " · part %d of %d of one message" % (piece.part, piece.parts) if piece.parts > 1 else "",
        )]
        if piece.before:
            flat = _flat(piece.before)
            block.append("Just before it, the agent said: %s%s" % ("…" if len(flat) > BEFORE else "", flat[-BEFORE:]))
        block.extend("> " + line for line in piece.text.split("\n"))
        block.append("")
        cost = sum(len(line) + 1 for line in block)
        if shown and size + cost > BUDGET:
            return shown, number
        shown.extend(block)
        size += cost
        number += 1
    return shown, None


def dated(conversation, found):
    """The day a conversation began, where its first piece says; else the day its file was last added to."""
    at = found[0].turn.at if found else ""
    return at[:10] if DAY.match(at) else conversation.dated


def first_words(found, most=80):
    flat = _flat(found[0].text) if found else ""
    return flat if len(flat) <= most else flat[:most - 3] + "..."


def quoted(text):
    """A name or a path as a command line takes it: as it is where it is plain, else between single
    quotes, which a shell reads as written."""
    return text if PLAIN.match(text) else "'%s'" % text.replace("'", "'\\''")
