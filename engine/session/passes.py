"""The learn pass: its state while it is open, the window it froze, and what sealing it writes.

A pass reads the observations that were open when it opened, and no others. Its state is one file
under `vesta/.state/`; what lasts of it is its note under `vesta/log/passes/` and the folder of
observations it archived.
"""
from __future__ import annotations

import json
import re

from kernel import ids
from kernel import tree as trees
from kernel.errors import Refusal, UsageError
from matchers import probes, triggers
from model.abstractions import DISPOSITION
from session import log, observations, pending
from stores import admissions, similar
from stores.filestore import ARCHIVE

PATH = "vesta/.state/pass.json"
LOG = "vesta/log/passes"
NAME = "pass-%03d"
NUMBERED = re.compile(r"pass-(\d+)(\.md)?\Z")
DIRECT = "direct"
READ = "read"
ENDINGS = ("dropped", "moot")
ENDING = re.compile(r"(%s)\s*(?:—|–|--|-|:)\s*(\S.*)\Z" % "|".join(ENDINGS), re.S)
HOLD_LIMIT = 3
RULE = "vesta/INTERNALS.md, Learn passes"

# The keys of the note file the agent gives to `pass seal`, and the line each becomes.
GROUPS, UNGROUPED, NOT_DONE, CONSOLIDATION, WAITING = "Groups", "Ungrouped", "Not done", "Consolidation", "Waiting"
NOTE_KEYS = (GROUPS, UNGROUPED, CONSOLIDATION, NOT_DONE)
OPENED, SEALED, REVIEW, RUN = "Opened", "Sealed", "Trigger review", "run"


class Pass(object):
    """One learn pass as its state file holds it. A walk runs in it as it would in a session."""

    ask_word = "The owner's question"

    def __init__(self, data):
        self.data = data

    number = property(lambda self: self.data["number"])
    id = property(lambda self: NAME % self.data["number"])
    opened = property(lambda self: self.data.get("opened", ""))
    window = property(lambda self: self.data.setdefault("window", []))
    asks = property(lambda self: self.data.setdefault("asks", []))
    disposed = property(lambda self: self.data.setdefault("disposed", []))
    reviewed = property(lambda self: self.data.get("trigger-review") is True)
    # The steps printed only where asked for that this pass has printed: every later part numbers them too.
    requested = property(lambda self: self.data.setdefault("requested", []))
    pairs = property(lambda self: self.data.get("pairs"))
    heading = property(lambda self: "Pass: %s, opened %s" % (self.id, self.opened))
    resume = ""


def read(tree):
    """The open pass, or None where none is open. Raises UsageError for a state file that does not read."""
    if not tree.is_file(PATH):
        return None
    try:
        data = json.loads(tree.read(PATH))
        if not isinstance(data, dict) or not isinstance(data.get("number"), int) or not isinstance(data.get("window", []), list):
            raise ValueError("it does not hold a pass")
    except (ValueError, UnicodeDecodeError) as error:
        raise UsageError(
            "%s does not read (%s). It is the engine's working state and no record: delete that one file by hand and run "
            "`walk learn` again, which opens a pass over the notes open now." % (PATH, error)
        )
    return Pass(data)


def save(tree, found):
    tree.write(PATH, json.dumps(found.data, indent=1, ensure_ascii=False) + "\n")


def current(tree, what):
    """The open pass a command needs. Raises Refusal where none is open."""
    found = read(tree)
    if found is None:
        raise Refusal("%s belongs to a learn pass, and none is open. `walk learn` opens one." % what, RULE)
    return found


def archive_folder(tree):
    """Where an observation that is finished with goes: the open pass's folder, else `direct`."""
    try:
        found = read(tree)
    except UsageError:
        found = None
    return "%s/%s" % (ARCHIVE, found.id if found is not None else DIRECT)


def numbers(context):
    """The numbers of the passes that left a note or an archive folder, in order."""
    found = set()
    for folder in [LOG] + ["%s/%s" % (store.path, ARCHIVE) for store in observations.stores_of(context)]:
        for name in context.tree.list(folder):
            match = NUMBERED.match(name)
            if match:
                found.add(int(match.group(1)))
    return sorted(found)


def note_path(number):
    return "%s/%s.md" % (LOG, NAME % number)


def note_of(tree, number):
    """What a sealed pass's note says, by the label each line opens with."""
    found = {}
    for line in tree.read_or(note_path(number)).split("\n"):
        if line.startswith("- ") and ": " in line:
            key, value = line[2:].split(": ", 1)
            found[key.strip()] = value.strip()
    return found


def last(context):
    """(the number of the newest sealed pass, when it opened, when it was sealed); None and empty
    texts where no pass has been sealed."""
    sealed = [number for number in numbers(context) if context.tree.is_file(note_path(number))]
    if not sealed:
        return None, "", ""
    value = note_of(context.tree, sealed[-1]).get(OPENED, "")
    opened = value.split(" · ")[0].strip()
    sealed_at = value.split("%s: " % SEALED)[-1].strip() if "%s: " % SEALED in value else ""
    return sealed[-1], opened, sealed_at


def since_review(context):
    """(the newest sealed pass that ran the trigger review or None, how many passes were sealed after it)."""
    sealed = [number for number in numbers(context) if context.tree.is_file(note_path(number))]
    for count, number in enumerate(reversed(sealed)):
        if note_of(context.tree, number).get(REVIEW, "").startswith(RUN):
            return number, count
    return None, len(sealed)


def open_now(context, ask=""):
    """(the pass a learn walk runs in, whether it was opened just now)."""
    found = read(context.tree)
    opened = found is None
    if opened:
        taken = numbers(context)
        window = [record.ref for store in observations.stores_of(context) for record in store.list() if observations.is_open(store, record)]
        found = Pass({"number": (taken[-1] if taken else 0) + 1, "opened": context.clock.timestamp(), "window": window, "asks": [], "disposed": []})
    before = json.dumps(found.data, sort_keys=True)
    if ask and ask not in found.asks:
        found.asks.append(ask)
    if opened or json.dumps(found.data, sort_keys=True) != before:
        save(context.tree, found)
    return found, opened


def records(context, found):
    """[(store, record)] for every observation of the window that is still in a store, in window order."""
    resolved = []
    takers = observations.stores_of(context)
    for ref in found.window:
        named = context.stores.resolve(ref)
        if named is not None and named[0] in takers:
            resolved.append(named)
    return resolved


def still_open(context, found):
    return [(store, record) for store, record in records(context, found) if observations.is_open(store, record)]


def sessions(context, found):
    """How many separate sessions the window's observations come from."""
    return len(set(str(record.get(observations.SESSION)) for _, record in records(context, found)))


def firing(context, found):
    """The open observations of the window whose `recheck` probe fires now."""
    fired = []
    for store, record in still_open(context, found):
        text = record.get(observations.RECHECK)
        if text and probes.evaluate(text, context).state == probes.FIRED:
            fired.append(record)
    return fired


def read_before(context, found, count=3):
    """[(store, record)] that the last passes before this one archived as read, newest pass first."""
    listed = []
    for number in [n for n in reversed(numbers(context)) if n < found.number][:count]:
        for store in observations.stores_of(context):
            for record in observations.listed(store, ARCHIVE, number):
                if str(store.type.life(record, DISPOSITION)).startswith(READ):
                    listed.append((store, record))
    return listed


def citing(context):
    """{an observation's internal id: the labels of the pending proposals that cite it as evidence}."""
    found = {}
    for _, record in pending.pending(context):
        for ref in record.texts(pending.EVIDENCE):
            uid = ids.parse_ref(ref)[1]
            named = context.stores.resolve(ref) if not uid else None
            uid = uid or (named[1].uid if named else "")
            if uid:
                found.setdefault(uid, []).append(record.label)
    return found


def pair_count(context):
    return sum(len(similar.pairs(store)) for store in context.stores.recalled())


# ------------------------------------------------------------------------------------------- dispose

def ending(text):
    """A disposition as it is written, from what the command line gave. Raises UsageError."""
    match = ENDING.match(" ".join(text.split()))
    if not match:
        raise UsageError(
            "`--as` takes `dropped — <reason>` or `moot — <reason>`: dropped for noise, moot for a note whose subject has left "
            "the project. A plain hyphen may stand for the dash."
        )
    return "%s — %s" % (match.group(1), match.group(2))


def dispose(context, found, name, text):
    """Set a terminal disposition on one open observation of the window and archive it.
    Returns (the record as archived, the disposition as written)."""
    text = ending(text)
    named = context.stores.resolve(name)
    window = set(ids.parse_ref(ref)[1] for ref in found.window)
    if named is None or named[0] not in observations.stores_of(context):
        raise UsageError("`%s` names no note; `obs list --open` prints the open ones" % name)
    store, record = named
    if record.uid not in window:
        raise Refusal("%s is not one of the notes %s reads: it was written after the pass opened, and waits for the next one." % (record.label, found.id), RULE)
    if not observations.is_open(store, record):
        raise Refusal("%s is already dealt with: %s. Nothing was changed." % (record.label, store.type.life(record, DISPOSITION)), RULE)
    cited = citing(context).get(record.uid)
    if cited:
        raise Refusal(
            "%s is evidence of %s, which waits for the owner. Deciding that proposal deals with the note; nothing was changed." % (record.label, ", ".join(cited)), RULE
        )
    changed = record.copy()
    changed.fields[store.type.life_field(DISPOSITION)] = text
    target = store.path_for(record.label, "%s/%s" % (ARCHIVE, found.id))
    overlay = trees.Overlay(context.tree)
    overlay.move(record.path, target)
    overlay.write(target, store.text(changed))
    overlay.commit()
    found.disposed.append(record.ref)
    save(context.tree, found)
    return changed, text


# ---------------------------------------------------------------------------------------------- seal

def note_given(text):
    """({key: value}, {an observation's label or id: what it waits for}) from the agent's note file.
    Raises UsageError for a line that is neither."""
    keys, waits = {}, {}
    for line in text.replace("\r\n", "\n").split("\n"):
        line = line.strip()
        line = line[2:].strip() if line.startswith("- ") else line
        if not line:
            continue
        name, _, value = line.partition(":")
        name, value = name.strip(), " ".join(value.split())
        if name.startswith(WAITING + " ") and value:
            waits[name[len(WAITING) + 1:].strip()] = value
        elif name in NOTE_KEYS and value:
            keys[name] = value
        else:
            raise UsageError(
                "the note file has a line that is not one of its own: `%s`. Its lines are `%s: <text>`, and `%s <id>: <what the note waits for>`."
                % (line[:80], "`, `".join("%s: <text>" % key for key in NOTE_KEYS)[:-len(": <text>")], WAITING)
            )
    return keys, waits


def _proposals(context, found):
    """What became of each proposal of the pass, as the pass note states it."""
    window = set(ids.parse_ref(ref)[1] for ref in found.window)
    decided = dict((ids.parse_ref(parts[1])[1], parts) for parts in admissions.lines(context.tree) if len(parts) >= 5)
    listed = []
    for store in pending.stores_of(context):
        held = list(store.list())
        for name in context.tree.list(pending.LOG):
            if name.endswith(".md") and not name.endswith(pending.DRAFT):
                try:
                    held.append(store.read("%s/%s" % (pending.LOG, name)))
                except Exception:  # a logged proposal that no longer reads is left out of the note, and `check` names it
                    continue
        for record in sorted(held, key=lambda record: ids.sort_key(record.label)):
            cites = set(ids.parse_ref(ref)[1] for ref in record.texts(pending.EVIDENCE))
            if record.get(pending.SOURCE) != found.id and not (cites & window):
                continue
            parts = decided.get(record.uid)
            if parts is None:
                listed.append("%s %s %s pending" % (record.label, record.get(pending.KIND), record.get(pending.TARGET)))
            elif parts[4].startswith(admissions.APPROVED):
                listed.append("%s %s → %s approved" % (record.label, parts[2], ids.parse_ref(parts[3])[0] or parts[3]))
            elif parts[4].startswith(admissions.STALE):
                listed.append("%s %s overtaken" % (record.label, parts[2]))
            else:
                listed.append("%s %s rejected" % (record.label, parts[2]))
    return listed


def _review(context, found):
    if not found.reviewed:
        return "not run"
    live = triggers.live(context, context.stores.recalled())
    fired = [item.name for item in live if item.state.state == probes.FIRED]
    return "%s — %d live, %d fired%s" % (RUN, len(live), len(fired), " (%s)" % ", ".join(fired) if fired else "")


def seal(context, found, hold=(), note=""):
    """Archive the window, write the pass note and remove the pass state, all or none.
    Returns (the note's path, the records held, the records archived)."""
    keys, waits = note_given(note)
    open_ones = still_open(context, found)
    by_name = {}
    for store, record in open_ones:
        by_name[record.label] = by_name[record.uid] = by_name[record.ref] = record.uid
    named, unknown = set(), []
    for name in list(hold) + list(waits):
        if name in by_name:
            named.add(by_name[name])
        else:
            unknown.append(name)
    if unknown:
        raise Refusal(
            "nothing was written: %s %s not a note of this pass that is still open. The ones still open are: %s."
            % (", ".join("`%s`" % name for name in unknown), "is" if len(unknown) == 1 else "are", ", ".join(record.label for _, record in open_ones) or "none"),
            RULE,
        )
    reasons = dict((by_name[name], reason) for name, reason in waits.items())
    cited = citing(context)
    overlay = trees.Overlay(context.tree)
    held, archived, lines = [], [], []
    for store, record in open_ones:
        changed = record.copy()
        before = record.texts(observations.HELD)
        keep = record.uid in named or (record.uid in cited and len(before) < HOLD_LIMIT)
        if keep:
            changed.fields[observations.HELD] = before + [found.id]
            overlay.write(record.path, store.text(changed))
            why = reasons.get(record.uid) or ("%s is waiting for the owner" % ", ".join(cited[record.uid]) if record.uid in cited else "no reason given")
            lines.append("%s (%s)" % (record.label, why))
            held.append(changed)
        else:
            changed.fields[store.type.life_field(DISPOSITION)] = "%s (%s)" % (READ, found.id)
            target = store.path_for(record.label, "%s/%s" % (ARCHIVE, found.id))
            overlay.move(record.path, target)
            overlay.write(target, store.text(changed))
            archived.append(changed)
    pairs = found.pairs if isinstance(found.pairs, int) else pair_count(context)
    consolidation = "%d pair%s found" % (pairs, "" if pairs == 1 else "s") if pairs else "no pair found"
    stamp = context.clock.timestamp()
    text = "\n".join([
        "# Pass %03d — %s" % (found.number, context.clock.today()),
        "",
        "- Window: %d observation%s from %d session%s" % (len(found.window), "" if len(found.window) == 1 else "s", sessions(context, found), "" if sessions(context, found) == 1 else "s"),
        "- %s: %s · %s: %s · Dropped as noise: %d" % (GROUPS, keys.get(GROUPS, "not stated"), UNGROUPED, keys.get(UNGROUPED, "not stated"), len(found.disposed)),
        "- Proposals: %s" % (" · ".join(_proposals(context, found)) or "none"),
        "- Held: %s" % (", ".join(lines) or "none"),
        "- %s: %s" % (REVIEW, _review(context, found)),
        "- %s: %s" % (CONSOLIDATION, consolidation + (", %s" % keys[CONSOLIDATION] if CONSOLIDATION in keys else "")),
        "- %s: %s" % (NOT_DONE, keys.get(NOT_DONE, "not stated")),
        "- %s: %s · %s: %s" % (OPENED, found.opened, SEALED, stamp),
        "",
    ])
    path = note_path(found.number)
    if context.tree.is_file(path):
        raise Refusal("nothing was written: %s is already there, and a pass note is never written over." % path, RULE)
    overlay.write(path, text)
    overlay.remove(PATH)
    overlay.commit()
    return path, held, archived


# ----------------------------------------------------------------------------------------- reminders

def closed_since(context):
    """How many sessions have closed since the last pass was sealed; every closed one where none was."""
    _, _, sealed_at = last(context)
    found = set()
    for entry in log.read(context.tree):
        if entry.get("mark") != log.UNCLOSED and str(entry.get("at", "")) >= sealed_at:
            found.add(entry.get("session"))
    return len(found)
