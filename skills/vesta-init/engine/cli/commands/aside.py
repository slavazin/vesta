"""`aside`: start a copy of the running conversation that notes a correction where the owner made one, and ends.

With no word it is what the harness runs each time the owner says something: it reads what the harness
sends on standard input, starts the copy, and prints nothing, whatever happens. `aside steer` and
`aside nothing` are what the copy runs to report back.
"""
from __future__ import annotations

import datetime
import json
import os
import signal
import subprocess
import sys
import time

from cli import args, sessions
from kernel.errors import Refusal, UsageError
from session import asides, harness, history, jotting, review, settings, state
from steps import base, instruction, sheet

REPORTS = {"steer": asides.NOTED, "nothing": asides.NOTHING}
# A copy that carries out a part is given this long in all; one run of the command waits this long, which
# is under what a harness gives a command by default, and is run again to go on waiting.
MINUTES, WAIT, PAUSE = 15, 90, 0.5
TEXT = "aside"
STOP = "--stop"
# What the detached process that holds a copy is started as; and what it writes down where the copy ended by itself.
HOLD, ENDED = "hold", "ended"
ENGINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def launch(command, environ, root):
    """Start a command and do not wait for it: returns what was started. Raises OSError where it cannot be."""
    options = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "cwd": root, "env": environ}
    if os.name == "nt":
        options["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    else:
        options["start_new_session"] = True
    return subprocess.Popen(command, **options)


def run_copy(command, environ, root, stopped):
    """Run a copy to its end, as the process that holds it. Returns "" where it ended by itself, else
    why it did not. `stopped` says whether the copy is no longer wanted; it is asked as the copy runs."""
    options = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "cwd": root, "env": environ}
    if os.name != "nt":
        options["start_new_session"] = True
    try:
        process = subprocess.Popen(command, **options)
    except (OSError, ValueError) as error:
        return "it could not be started (%s)" % " ".join(str(error).split())[:200]
    began = time.monotonic()
    while process.poll() is None:
        late = time.monotonic() - began > MINUTES * 60
        if late or stopped():
            # The copy is this process's own child, in a group of its own: the whole group is ended.
            try:
                os.killpg(process.pid, signal.SIGTERM) if os.name != "nt" else process.terminate()
            except OSError:
                pass
            return "it was stopped after %d minutes" % MINUTES if late else "it was stopped"
        time.sleep(1)
    return ""


def pause():
    time.sleep(PAUSE)


def _adopted(context, sent):
    """The environment of the harness that sent this, where it was sent by one that can start a copy
    and the command's own environment does not say so."""
    for name in context.known.get(harness.TABLE, ()):
        found = context.member(harness.TABLE, name)(context.environ).adopt(sent)
        if found is not None:
            return found
    return None


def _hook(context):
    if context.environ.get(asides.TOKEN):
        return 0
    try:
        sent = json.loads(args.read_stdin(context.stdin))
    except (ValueError, UsageError, RecursionError):
        return 0
    if not isinstance(sent, dict):
        return 0
    if jotting.in_effect(context) != jotting.ASIDE:
        adopted = _adopted(context, sent)
        if adopted is None:
            return 0
        context.environ = adopted
        if jotting.in_effect(context) != jotting.ASIDE:
            return 0
    running = harness.current(context)
    conversation, words = running.said(sent)
    if not conversation or not words.strip():
        return 0
    bound = state.bound(context.tree, running.id, conversation)
    name, at = os.urandom(6).hex(), context.clock.timestamp()
    asides.started(context.tree, name, at, conversation, bound[-1].id if bound else "", words.strip()[:asides.WORDS])
    line = sheet.command_line(context)
    quoted = "\n".join("> " + part for part in words.strip()[:asides.WORDS].split("\n"))
    prompt = instruction.fill(instruction.read(TEXT), context, {"words": "\n" + quoted + "\n", "command": line})
    try:
        launch(running.fork(conversation, prompt, [line + " " + TEXT]), dict(context.environ, **{asides.TOKEN: name, running.ORIGINAL: conversation}), context.root)
    except (OSError, ValueError) as error:
        asides.answer(context.tree, name, "%s: %s" % (asides.FAILED, " ".join(str(error).split())[:200]))
    return 0


def _session(context, entry):
    """(the session a correction a copy found goes into, whether it was opened just now): the one the
    copy's start was bound to, else the latest one open from that conversation, else the one open
    session, else a late one, which is told which conversation it belongs to."""
    running = harness.current(context)
    held = state.read(context.tree, entry["session"]) if entry["session"] else None
    if held is None or held.status != state.OPEN or held.origin is not None:
        bound = state.bound(context.tree, running.id, entry["conversation"]) if running is not None else []
        held = bound[-1] if bound else None
    session, opened = sessions.current_or_late(context, {sessions.OPTION: held.id} if held is not None else {})
    sessions.ordinary(session, "a correction")
    if opened and running is not None:
        session = state.update(context.tree, session, lambda fresh: state.bind(fresh, running.id, entry["conversation"]))
    return session, opened


def _report(context, word):
    name = context.environ.get(asides.TOKEN) or ""
    entry, took = asides.claim(context.tree, name, REPORTS[word]) if name else (None, False)
    if entry is None:
        raise Refusal("`aside %s` is what a copy of a conversation runs to report back, and this command was not started by one. "
                      "The start of a task says how a correction is noted. Nothing was noted." % word, settings.RULE)
    if not took:
        context.write("This copy has already reported: %s. Nothing was changed. Stop now." % entry["answer"])
        return 0
    if REPORTS[word] != asides.NOTED:
        context.write("Written down: nothing to note. Stop now.")
        return 0
    try:
        session, opened = _session(context, entry)
        session = context.session = state.update(context.tree, session, lambda fresh: fresh.jot(entry["at"], entry["words"], True, ""))
    except (Refusal, UsageError) as error:
        why = " ".join(str(getattr(error, "message", error)).split())
        asides.answer(context.tree, name, "%s: %s" % (asides.FAILED, why[:200]), force=True)
        context.write("The correction could not be noted (%s). It is read back when the task is reviewed. Stop now." % why[:300])
        return 0
    context.write("Noted in %s as a correction from the owner%s. Stop now." % (session.id, ", which was opened late to hold it" if opened else ""))
    return 0


def _age(context, started):
    try:
        then = datetime.datetime.strptime(started, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    except (ValueError, TypeError):
        return MINUTES * 60 + 1
    return (context.clock.now() - then).total_seconds()


def _forwarded(options):
    """The walk's own options, as the copy's command and this command's later runs take them."""
    text = " --short" if "--short" in options else ""
    for name in ("--paths", "--with"):
        if options.get(name):
            text += " %s %s" % (name, " ".join(history.quoted(value) for value in options[name]))
    return text


def _checkpoint(context, words, options):
    known = context.known.get("walks-aside", ())
    if len(words) != 2 or words[1] not in known or words[1] not in context.config.checkpoints:
        raise UsageError("`aside walk` takes one of the walks a copy may carry out the first part of: %s" % (", ".join(known) or "none"))
    checkpoint = context.config.checkpoints[words[1]]
    if "--short" in options and not checkpoint.short:
        raise UsageError("the `%s` walk has no short form" % checkpoint.id)
    return checkpoint


def _mine(session, name):
    """The record of the copy of that name on a session, or None where the session holds another or none."""
    found = state.copy_of(session)
    return found if found is not None and found["id"] == name else None


def _drop(context, session, name):
    """Take a copy's record off its session, where the session still holds that copy."""
    return state.update(context.tree, session, lambda fresh: fresh.data.pop(state.COPY, None) if _mine(fresh, name) else None)


def _next(context, checkpoint, session, options):
    if session.status != state.CLOSED:
        return "It was left unfinished, so no part of its review is left to carry out."
    following = sheet.following(context, sheet.Walk(checkpoint, session, short="--short" in options, requested=options.get("--with", [])))
    if following is None:
        return "The walk has no further part. Tell the owner how many notes were written, by their titles."
    return "**Do:** Print the next part with `walk %s%s --from %s%s`, and carry it out here." % (
        checkpoint.id, " --short" if "--short" in options else "", following.id, session.resume)


def _walk(context, words, options):
    checkpoint = _checkpoint(context, words, options)
    session = sessions.ordinary(sessions.current(context, options), "this walk")
    forwarded = _forwarded(options)
    again = "`aside walk %s%s%s`" % (checkpoint.id, forwarded, session.resume)
    back = "`walk %s --here%s%s` prints the part to carry out here." % (checkpoint.id, forwarded, session.resume)
    copy = state.copy_of(session)
    if STOP in options:
        if copy is None:
            context.write("No copy is carrying out a part for %s, so nothing was stopped. %s" % (session.id, back))
            return 0
        # The process that holds the copy ends it once the record is gone.
        _drop(context, session, copy["id"])
        context.write("The copy that was carrying out the part for %s is being stopped. What it wrote stays. %s" % (session.id, back))
        return 0
    if copy is None:
        if session.status != state.OPEN:
            context.write("%s is %s: the part is done with, and no copy was started. %s" % (session.id, session.status, _next(context, checkpoint, session, options)))
            return 0
        if context.environ.get(asides.TOKEN):
            raise Refusal("this command was started by a copy of a conversation, and a copy starts no copy. Nothing was started. %s" % back, settings.RULE)
        if review.in_effect(context) != review.ASIDE:
            raise Refusal("the setting `review` is not `aside` here: %s. Nothing was started. %s" % (
                settings.said(settings.resolve(context, review.ID, None if _reads(context) else {})), back), settings.RULE)
        running = harness.current(context)
        fresh_copy = {"id": os.urandom(6).hex(), "started": context.clock.timestamp(), "minted": len(session.minted)}

        def begin(fresh):
            # Decided on the session as its file holds it now: of several runs at once, one starts a copy and the rest wait for it.
            if state.copy_of(fresh) is not None or fresh.status != state.OPEN:
                return
            if not state.conversation_of(fresh):
                # A session opened at the review holds no conversation yet; the copy is told which one it reads back.
                state.bind(fresh, running.id, running.conversation())
            fresh.data[state.COPY] = fresh_copy
        session = context.session = state.update(context.tree, session, begin)
        copy = state.copy_of(session)
        if copy is not None and copy["id"] == fresh_copy["id"]:
            holder = [sys.executable, ENGINE, TEXT, HOLD, checkpoint.id] + (["--short"] if "--short" in options else [])
            for name in ("--paths", "--with"):
                if options.get(name):
                    holder.extend([name] + list(options[name]))
            environ = dict(context.environ, **{asides.TOKEN: copy["id"], running.ORIGINAL: running.conversation()})
            try:
                launch(holder + [sessions.OPTION, session.id], environ, context.root)
            except (OSError, ValueError) as error:
                _drop(context, session, copy["id"])
                context.write("# The part carried out aside")
                context.write()
                context.write("The copy could not be started (%s). Nothing was written. Carry the part out here: %s" % (" ".join(str(error).split())[:200], back))
                return 0
    waited, now, late = 0.0, copy, False
    while copy is not None:
        session = state.named(context.tree, session.id)
        now = _mine(session, copy["id"])
        # A copy that has said nothing a minute past its time is taken for lost.
        late = _age(context, copy["started"]) > MINUTES * 60 + 60
        if session.status != state.OPEN or now is None or now.get("ended") or late or waited >= WAIT:
            break
        pause()
        waited += PAUSE
    session = context.session = state.named(context.tree, session.id)
    context.write("# The part carried out aside")
    context.write()
    if copy is None:
        context.write("%s is %s: the part is done with. %s" % (session.id, session.status, _next(context, checkpoint, session, options)))
        return 0
    written = session.minted[copy["minted"]:] if copy["minted"] <= len(session.minted) else []
    context.write("Notes the copy wrote: %s" % (len(written) or "none"))
    for entry in written:
        context.write(base.minted_line(entry))
    context.write()
    ended = now is None or bool(now.get("ended"))
    if session.status == state.OPEN and not ended and not late:
        context.write("The copy is still at work; it was started %s. **Do:** Run %s again to go on waiting, and nothing else of Vesta's meanwhile. "
                      "`aside walk %s %s%s` ends the copy." % (copy["started"], again, checkpoint.id, STOP, session.resume))
        return 0
    _drop(context, session, copy["id"])
    if session.status == state.OPEN:
        why = (now or {}).get("ended") or ""
        why = why if why and why != ENDED else "nothing was heard from it %d minutes after it was started" % (MINUTES + 1) if late and not ended else \
            "it was stopped" if now is None else "it ended before the session was closed"
        context.write("The copy did not finish the part: %s. %s is still open, and what the copy wrote stays. Carry the part out here: %s" % (why, session.id, back))
        return 0
    context.write("The copy finished the part, and %s is %s." % (session.id, session.status))
    context.write(_next(context, checkpoint, session, options))
    return 0


def _hold(context, words, options):
    """What the detached process does: it runs the copy to its end and writes down how it ended.
    Started by `aside walk` only; anything else that runs it finds no copy of its name and does nothing."""
    checkpoint = _checkpoint(context, words, options)
    session = state.named(context.tree, options.get(sessions.OPTION))
    name = context.environ.get(asides.TOKEN) or ""
    copy = _mine(session, name)
    running = harness.current(context)
    if copy is None or copy.get("ended") or running is None or not running.forks:
        return 0
    context.session = session
    line = sheet.command_line(context)
    prompt = instruction.fill(instruction.read("aside-walk"), context, {"command": line, "walk": checkpoint.id, "options": _forwarded(options) + session.resume})

    def stopped():
        try:
            return _mine(state.named(context.tree, session.id), name) is None
        except UsageError:
            return False
    why = run_copy(running.fork(running.conversation(), prompt, [line], reads=True), dict(context.environ), context.root, stopped)

    def end(fresh):
        if _mine(fresh, name) is not None:
            fresh.data[state.COPY]["ended"] = why or ENDED
    state.update(context.tree, session, end)
    return 0


def _reads(context):
    try:
        settings.read(context.tree)
    except UsageError:
        return False
    return True


def run(context, arguments):
    if arguments[:1] in (["walk"], [HOLD]):
        words, options = args.split(arguments, flags=("--short", STOP), options=(sessions.OPTION,), many=("--paths", "--with"), takes=True)
        return _walk(context, words, options) if arguments[0] == "walk" else _hold(context, words, options)
    words, _ = args.split(arguments, takes=True)
    if not words:
        return _hook(context)
    if len(words) != 1 or words[0] not in REPORTS:
        raise UsageError("`aside` takes one of: %s, or `walk <checkpoint>`; with no word it is what the harness runs each time the owner says something" % ", ".join(REPORTS))
    return _report(context, words[0])
