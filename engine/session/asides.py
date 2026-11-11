"""Copies of a conversation started aside: each time one is started it is written down here, and
again when it reports back, so that a review can tell a copy that found nothing from one that never ran."""
from __future__ import annotations

import json

from kernel.errors import UsageError

PATH = "vesta/.state/asides.json"
LOCK = "vesta/.state/asides.lock"
ASIDES = "asides"
# Set in the environment of a copy, to the name its start was written down under.
TOKEN = "VESTA_ASIDE"
NOTED, NOTHING, FAILED = "noted", "nothing", "failed"
KEPT = 500
# How much of what the owner said is kept with a copy.
WORDS = 4000


def _reads(entry):
    return isinstance(entry, dict) and all(isinstance(entry.get(name), str) for name in ("id", "at", "conversation", "session", "answer", "words"))


def read(tree):
    """Every copy started, oldest first. Raises UsageError where the file does not read."""
    if not tree.is_file(PATH):
        return []
    try:
        data = json.loads(tree.read(PATH))
    except (ValueError, UnicodeDecodeError, RecursionError):
        data = None
    found = data.get(ASIDES) if isinstance(data, dict) else None
    if not isinstance(found, list) or not all(_reads(entry) for entry in found):
        raise UsageError(
            "%s does not read. It is the engine's working state and no record, so this one file may be deleted by hand; "
            "what the owner said is then read back when a task is reviewed. Then run the command again." % PATH
        )
    return found


def _change(tree, change):
    with tree.lock(LOCK) as held:
        if not held:
            raise UsageError("another command is writing down a copy at this moment; nothing was written. Run this command again.")
        found = read(tree)
        result = change(found)
        tree.write(PATH, json.dumps({ASIDES: found[-KEPT:]}, indent=1, sort_keys=True) + "\n")
        return result


def started(tree, name, at, conversation, session, words):
    """`session` is the task's session opened from that conversation, or an empty text; `words` what the owner said."""
    _change(tree, lambda found: found.append({"id": name, "at": at, "conversation": conversation, "session": session, "answer": "", "words": words}))


def answer(tree, name, said, force=False):
    """Write down what became of a copy where nothing is written down yet; `force` writes over what is.
    Returns whether a copy of that name was started."""
    def change(found):
        for entry in found:
            if entry["id"] == name:
                if not entry["answer"] or force:
                    entry["answer"] = said
                return True
        return False
    return _change(tree, change)


def claim(tree, name, said):
    """Take a copy's one report, under the lock. Returns (the entry as it was, whether this call took
    it); (None, False) where no copy of that name was started."""
    def change(found):
        for entry in found:
            if entry["id"] == name:
                before = dict(entry)
                if entry["answer"]:
                    return before, False
                entry["answer"] = said
                return before, True
        return None, False
    return _change(tree, change)


def of(tree, conversation, since=""):
    """The copies started from a conversation at or after a moment."""
    return [entry for entry in read(tree) if entry["conversation"] == conversation and entry["at"][:19] >= since[:19]]
