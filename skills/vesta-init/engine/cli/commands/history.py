"""`history`: where conversations held before now are kept, which ones are there, and what was said in one.
`forget` drops the record that one was read back; the rest read and never write."""
from __future__ import annotations

import re

from cli import args
from kernel.errors import Refusal, UsageError
from model.abstractions import HistoryError
from session import harness, history, state
from steps import earlier, instruction

ACTS = ("sources", "where", "list", "turns", "forget")
LAST, MOST = 5, 20
# How many files `list` opens at the most, looking for the ones that hold something new; how many
# it names of the ones that do not read.
SCANNED, NAMED = 2000, 3
NUMBER = re.compile(r"[0-9]{1,9}\Z")


def _sources(context, given):
    readings = history.read(context.tree)
    known = set(entry["conversation"] for entry in readings if history.counts(context.tree, entry))
    context.write("# Where earlier conversations are read from")
    context.write()
    tried = []
    for name in history.sources(context):
        cls = context.member(history.TABLE, name)
        if cls.needs_path and not given:
            context.write("- `%s`: %s. Give the path as `history sources %s <path>`." % (name, cls.name, history.PATH_OPTION))
            continue
        # With a path, only the path is looked at: the owner named it, and no other place.
        tried.extend([(name, cls, given)] if given and cls.takes_path else [(name, cls, "")] if not given else [])
    for name, cls, path in tried:
        found = cls(context.root, path)
        option = " with `%s %s`" % (history.PATH_OPTION, history.quoted(path)) if path else ""
        try:
            conversations = found.conversations()
        except HistoryError as error:
            context.write("- `%s`%s: %s. Nothing was found: %s." % (name, option, cls.name, error))
            continue
        before = len([one for one in conversations if history.key(found, one) in known])
        places = " and ".join(place.replace("\\", "/") for place in found.places())
        context.write("- `%s`%s: %s, in %s. %d file%s, of which %d read back before, in full or in part.%s Not found by it: %s."
                      % (name, option, cls.name, places, len(conversations), "" if len(conversations) == 1 else "s", before,
                         " Passed over: %s." % found.left_out if found.left_out else "", cls.residue))
    context.write()
    context.write("Only the names and dates of files were read for this list; no conversation was opened, so a file that holds nothing is counted too.")
    context.write("`history list <place>` opens the latest ones to show how each begins.")
    return 0


def _where(context, given):
    """What to ask the owner before any place is looked at. Reads no file and lists no folder."""
    context.write("# Where to read earlier conversations from")
    context.write()
    if given:
        context.write("A path was given. Run `history sources %s %s`: it looks at that path and nowhere else, and says what each place finds there: "
                      "%s. Use the place that fits what the owner said the path holds; every later command takes that place and `%s %s`. "
                      "A path that is not absolute is read from the project root."
                      % (history.PATH_OPTION, history.quoted(given),
                         "; ".join("`%s` for %s" % (name, context.member(history.TABLE, name).name) for name in history.sources(context)),
                         history.PATH_OPTION, history.quoted(given)))
        return 0
    running = harness.current(context)
    kept = running.history if running is not None else ""
    if kept in history.sources(context):
        folder = " or ".join(place.replace("\\", "/") for place in history.member(context, kept).places())
        context.write(instruction.fill(instruction.read("history-where"), context, {"folder": folder, "name": running.name}))
    else:
        context.write(instruction.fill(instruction.read("history-where-unknown"), context))
    return 0


def _number(options, name, default, most=None):
    value = options.get(name)
    if value is None:
        return default
    if not NUMBER.match(value) or int(value) < 1 or (most is not None and int(value) > most):
        raise UsageError("`%s` takes a whole number from 1%s" % (name, " to %d" % most if most else " up"))
    return int(value)


def _list(context, found, options):
    last = _number(options, "--last", LAST, MOST)
    readings = history.read(context.tree)
    done = history.marks_read(context.tree, readings)
    conversations, passed = history.listed(found)
    shown, reading, read_back, empty, unreadable, opened = [], [], 0, 0, [], 0
    # The conversation this command was started from is still being held: it is reviewed, not read back.
    running = harness.current(context)
    current = running.conversation() if running is not None and running.history == found.id and not found.given else ""
    current = current if any(one.ref == current for one in conversations) else ""
    for one in reversed(conversations):
        if len(shown) == last or opened == SCANNED:
            break
        if one.ref == current:
            continue  # said below, and counted in neither number
        opened += 1
        try:
            turns = found.turns(one)
        except HistoryError:
            unreadable.append(one.ref)
            continue
        mine = history.mine(turns)
        fresh = set(turn.mark for turn in mine if turn.mark not in done)
        if not mine:
            empty += 1
        elif history.being_read(context.tree, readings, history.key(found, one)) is not None:
            session = history.being_read(context.tree, readings, history.key(found, one))
            reading.append("- `%s` · %s · %s is open for it: `walk backfill --session %s` goes on with it" % (
                one.ref, history.dated(one, history.pieces(turns)) or "day not known", session.id, session.id))
        elif not fresh:
            read_back += 1
        else:
            pieces = history.pieces(turns, fresh)
            shown.append("- `%s` · %s · %d piece%s to read%s · opens: %s" % (
                one.ref, history.dated(one, pieces) or "day not known", len(pieces), "" if len(pieces) == 1 else "s",
                "; the rest of it was read back before or is being read" if len(fresh) != len(mine) else "", history.first_words(history.pieces(turns)),
            ))
    context.write("# Earlier conversations of `%s` with something to read back" % found.id)
    context.write()
    for line in shown or ["none"]:
        context.write(line)
    context.write()
    context.write("Listed, newest first: %d. Up to %d were asked for (`--last <n>` takes up to %d). Read them oldest first." % (len(shown), last, MOST))
    if current:
        context.write("Left out: `%s`, the conversation this command was started from. It is read at its own review." % current)
    if reading:
        context.write("Left open by an earlier run, and not among the ones listed:")
        for line in reading:
            context.write(line)
    conversations = [one for one in conversations if one.ref != current]
    context.write("Opened to find them: %d of %d file%s. Of those, read back in full before: %d; holding nothing to read: %d; not readable: %d."
                  % (opened, len(conversations), "" if len(conversations) == 1 else "s", read_back, empty, len(unreadable)))
    if unreadable:
        context.write("Not readable: %s%s. `history turns %s <name>` says why for one." % (
            ", ".join("`%s`" % name for name in unreadable[:NAMED]),
            " and %d more" % (len(unreadable) - NAMED) if len(unreadable) > NAMED else "", found.id))
    if opened < len(conversations):
        context.write("Not looked at: the %d oldest files; this command opens %d at the most." % (len(conversations) - opened, SCANNED))
    if passed:
        context.write("Passed over without being opened: %s." % passed)
    return 0


def _turns(context, found, words, options):
    if len(words) != 3:
        raise UsageError("`history turns` takes a place and a conversation, as `history turns claude-code <name> --at 21`")
    if history.SESSION_OPTION in options:
        session = state.named(context.tree, options[history.SESSION_OPTION])
        origin = session.origin or {}
        if session.origin is None:
            # A task's session, which read its own conversation back at its review.
            conversation = history.find(found, words[2])
            marks = history.held(history.read(context.tree), session.id, history.key(found, conversation))
            if not marks:
                raise UsageError("%s read nothing back from that conversation" % session.id)
            pieces = history.pieces(history.said(found, conversation), set(marks))
        elif (origin.get("history"), origin.get("conversation"), origin.get("in") or "") != (found.id, words[2], found.given):
            raise UsageError("%s was not opened to read back that conversation" % session.id)
        else:
            _, _, pieces = earlier.of_session(context, session)
    else:
        pieces = history.pieces(history.said(found, history.find(found, words[2])))
    start = _number(options, "--at", 1)
    if start > max(len(pieces), 1):
        raise UsageError("`--at %d` is past the end: there %s %d piece%s" % (start, "is" if len(pieces) == 1 else "are", len(pieces), "" if len(pieces) == 1 else "s"))
    shown, following = history.lines(pieces, start)
    for line in shown:
        context.write(line)
    if following is not None:
        context.write("Printed %d to %d of %d. The next start at `--at %d`." % (start, following - 1, len(pieces), following))
    else:
        context.write("Printed %d to %d of %d: that is the end." % (min(start, len(pieces)), len(pieces), len(pieces)))
    return 0


def _forget(context, found, words):
    if len(words) != 3:
        raise UsageError("`history forget` takes a place and a conversation, as `history forget claude-code <name>`")
    conversation = history.find(found, words[2])
    marks = [turn.mark for turn in history.mine(history.said(found, conversation))]
    count = history.forget(context.tree, history.key(found, conversation), marks)
    if not count:
        context.write("Nothing was recorded for `%s`, so nothing was changed: it is offered as it stands." % conversation.ref)
    else:
        context.write("Dropped %d reading%s that held what was said in `%s`: it is offered again in full, and so is any other "
                      "conversation that holds the same words. Notes already written from it stay; reading it again may write the "
                      "same thing a second time, so tell the owner." % (count, "" if count == 1 else "s", conversation.ref))
    return 0


def run(context, arguments):
    words, options = args.split(arguments, options=(history.PATH_OPTION, history.SESSION_OPTION, "--last", "--at"), takes=True)
    act = words[0] if words else "sources"
    if act not in ACTS:
        raise UsageError("`history` takes one of: %s" % ", ".join(ACTS))
    if options.get(history.PATH_OPTION) == "":
        raise UsageError("`%s` was given no path" % history.PATH_OPTION)
    given = options.get(history.PATH_OPTION, "")
    if act == "where":
        if len(words) > 1:
            raise UsageError("`history where` takes no `%s`" % words[1])
        return _where(context, given)
    if act == "sources":
        if len(words) > 1:
            raise UsageError("`history sources` takes no `%s`" % words[1])
        return _sources(context, given)
    if len(words) < 2:
        raise UsageError("`history %s` takes a place; `history` prints the places" % act)
    found = history.member(context, words[1], given)
    if act == "list":
        if len(words) != 2:
            raise UsageError("`history list` takes one place and no `%s`" % words[2])
        return _list(context, found, options)
    if act == "forget":
        return _forget(context, found, words)
    return _turns(context, found, words, options)
