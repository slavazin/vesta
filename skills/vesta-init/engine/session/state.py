"""Session state: the working memory of one session, one JSON file under `vesta/.state/sessions/`."""
from __future__ import annotations

import json
import os
import re

from kernel import ids
from kernel import root as roots
from kernel import tree as trees
from kernel.errors import Refusal, UsageError
from model.abstractions import SourceError

FOLDER = "vesta/.state/sessions"
OPEN, CLOSED, ABANDONED = "open", "closed", "abandoned"
SCOPE, INDEX, TRIGGER, SWEEP = "scope", "index", "trigger", "sweep"
LOADERS = (INDEX, TRIGGER)
APPLIED, NOT_APPLICABLE, SHOULD_HAVE_LOADED = "applied", "not-applicable", "should-have-loaded"
MARKS = (APPLIED, NOT_APPLICABLE, SHOULD_HAVE_LOADED)
ID = re.compile(r"S-[0-9]{8}-[0-9a-f]{4}\Z")
RULE = "vesta/INTERNALS.md, Sessions"
# What no change source reports, whatever it reads: the engine's working state and its own code.
ENGINE_OWNED = tuple(trees.HOME + name + "/" for name in roots.ENGINES) + (trees.STATE,)


class Session(object):
    """One session as its file holds it."""

    def __init__(self, data):
        self.data = data

    id = property(lambda self: self.data["id"])
    opened = property(lambda self: self.data.get("opened", ""))
    late = property(lambda self: self.data.get("late") is True)
    status = property(lambda self: self.data.get("status", OPEN))
    asks = property(lambda self: self.data.setdefault("asks", []))
    base = property(lambda self: self.data.setdefault("base", {}))
    loaded = property(lambda self: self.data.setdefault("loaded", []))
    probes = property(lambda self: self.data.setdefault("probes", {}))
    jots = property(lambda self: self.data.setdefault("jots", []))
    written = property(lambda self: self.data.setdefault("written", []))
    minted = property(lambda self: self.data.setdefault("minted", []))
    # How a walk sheet names what it runs in, and how the command for its next part finds it again.
    ask_word = "Task"
    requested = ()
    heading = property(lambda self: "Session: %s" % self.id)
    resume = property(lambda self: " --session %s" % self.id)

    def entry(self, record):
        """The loaded-list entry of a record, found by its internal id, or None."""
        for entry in self.loaded:
            if ids.parse_ref(entry.get("record", ""))[1] == record.uid:
                return entry
        return None

    def load(self, record, by):
        """Add a record to the loaded list. A record already there keeps its first `by`. Returns
        whether it was added."""
        if self.entry(record) is not None:
            return False
        self.loaded.append({"record": record.ref, "by": by, "mark": ""})
        return True

    def jot(self, at, text, steer=False, anchor=""):
        self.jots.append({"at": at, "steer": bool(steer), "text": text, "anchor": anchor})

    def one_line(self):
        """The session in one line, for a list a person or an agent chooses from."""
        ask = self.asks[-1] if self.asks else "no task recorded"
        ask = ask if len(ask) <= 80 else ask[:77] + "..."
        jots = len(self.jots)
        return "%s, opened %s, %d jot%s, task: %s" % (self.id, self.opened, jots, "" if jots == 1 else "s", " ".join(ask.split()))


def new_id(clock, taken=(), random=os.urandom):
    """`S-YYYYMMDD-` and four random hexadecimal characters, drawn again while taken."""
    while True:
        name = "S-%s-%s" % (clock.today().replace("-", ""), random(2).hex())
        if name not in taken:
            return name


def path_of(name):
    return "%s/%s.json" % (FOLDER, name)


def read(tree, name):
    """The session of that id, or None where there is none."""
    if not ID.match(name) or not tree.is_file(path_of(name)):
        return None
    try:
        data = json.loads(tree.read(path_of(name)))
    except (ValueError, UnicodeDecodeError):
        data = None
    if not isinstance(data, dict) or data.get("id") != name:
        raise UsageError(
            "%s does not read as a session. It is the engine's working state and no record, so this one file may be deleted by hand; then run the command again."
            % path_of(name)
        )
    return Session(data)


LOCK = FOLDER + "/.lock"


def update(tree, session, change):
    """Apply a change to a session as its file holds it now, under a lock, so that two commands
    running at once both land. Returns the session as saved."""
    with tree.lock(LOCK) as held:
        if not held:
            # Writing without the lock could drop what another command is writing at this moment.
            raise UsageError("another command is writing to this session at this moment; nothing was written. Run this command again.")
        fresh = read(tree, session.id) or session
        change(fresh)
        save(tree, fresh)
    return fresh


def save(tree, session):
    tree.write(path_of(session.id), json.dumps(session.data, indent=1, ensure_ascii=False) + "\n")


def every(tree):
    """Every session there is a file for, oldest first."""
    found = []
    for leaf in tree.list(FOLDER):
        if leaf.endswith(".json"):
            try:
                session = read(tree, leaf[:-len(".json")])
            except UsageError:
                continue
            if session is not None:
                found.append(session)
    return sorted(found, key=lambda session: (session.opened, session.id))


def unreadable(tree):
    """The session files that do not read. A command that does not name one works without it."""
    found = []
    for leaf in tree.list(FOLDER):
        if leaf.endswith(".json"):
            try:
                read(tree, leaf[:-len(".json")])
            except UsageError:
                found.append(path_of(leaf[:-len(".json")]))
    return found


def open_ones(tree):
    return [session for session in every(tree) if session.status == OPEN]


def create(context, ask="", late=False):
    """Open a session: a fresh id, the ask, and the base the change source marks now."""
    tree = context.tree
    taken = [leaf[:-len(".json")] for leaf in tree.list(FOLDER)]
    base, note = mark_base(context)
    session = Session({
        "id": new_id(context.clock, taken),
        "opened": context.clock.timestamp(),
        "late": bool(late),
        "status": OPEN,
        "asks": [ask] if ask else [],
        "base": base,
        "loaded": [],
        "probes": {},
        "jots": [],
        "written": [],
        "minted": [],
    })
    if note:
        session.data["base-note"] = note
    save(tree, session)
    return session


def mark_base(context):
    """(the base, a note where the base could not be taken)."""
    try:
        source, _ = context.change_source()
        return source.mark(), ""
    except SourceError as error:
        return {"source": ""}, str(error)


def base_lines(session):
    """What to say where a session opened without a base."""
    note = session.data.get("base-note")
    return ["The files this session changes will not be known: %s. `doctor` says more." % note] if note else []


def changed(context, session):
    """(the paths changed since the session's base, less what the engine wrote; why they could not be read)."""
    base = session.base
    if not base.get("source"):
        return [], session.data.get("base-note") or "no base was recorded when the session opened"
    try:
        source, _ = context.change_source(base["source"])
        paths = source.changed_since(base)
    except (SourceError, UsageError) as error:
        return [], str(error)
    own = set(session.written)
    return [path for path in paths if path not in own and not (path + "/").startswith(ENGINE_OWNED)], ""


def named(tree, name):
    """The session of an id the command line gave. Raises UsageError where there is none."""
    session = read(tree, name) if isinstance(name, str) else None
    if session is None:
        known = ", ".join(s.id for s in every(tree)) or "none"
        raise UsageError("`%s` is not a session of this project; the sessions are: %s" % (name, known))
    return session


def current(tree, name=None):
    """The session a command means: the one named, else the one open session.

    Raises Refusal where none is open or several are and none was named.
    """
    if name:
        return named(tree, name)
    found = open_ones(tree)
    if len(found) == 1:
        return found[0]
    if not found:
        raise Refusal("no session is open. `walk start` opens one; a command that reads a closed session takes `--session <id>`.", RULE)
    raise Refusal(
        "%d sessions are open, so the command must say which it means with `--session <id>`:\n%s"
        % (len(found), "\n".join("- " + session.one_line() for session in found)),
        RULE,
    )
