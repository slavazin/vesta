"""The consultation log: one line per loaded record, appended when a session closes or is abandoned.

It is the durable trace of which records a session read and what came of each.
"""
from __future__ import annotations

import json

from session import state

PATH = "vesta/log/consultations.jsonl"
UNMARKED, UNCLOSED, NONE_MATCHED = "unmarked", "unclosed", "none-matched"


def lines_for(session, at, status):
    """The log lines a session ends with: one per loaded record, or one saying nothing was loaded."""
    found = []
    for entry in session.loaded:
        mark = UNCLOSED if status == state.ABANDONED else (entry.get("mark") or UNMARKED)
        found.append({"session": session.id, "at": at, "record": entry.get("record", ""), "by": entry.get("by", ""), "mark": mark})
    if not found:
        found.append({"session": session.id, "at": at, "record": "", "by": "", "mark": UNCLOSED if status == state.ABANDONED else NONE_MATCHED})
    return found


def end(context, session, status):
    """Log the session's loaded records and set it closed or abandoned. Returns the lines written."""
    # A session that read back an earlier conversation was no task: it loaded nothing, and says nothing here.
    lines = lines_for(session, context.clock.timestamp(), status) if session.origin is None or session.loaded else []
    if lines:
        context.tree.append(PATH, "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines))
    session.data["status"] = status
    session.data["ended"] = context.clock.timestamp()
    if lines:
        session.written.append(PATH)
    state.save(context.tree, session)
    return lines


def read(tree):
    """Every line of the log that reads, in order."""
    found = []
    for line in tree.read_or(PATH).split("\n"):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if isinstance(entry, dict):
            found.append(entry)
    return found
