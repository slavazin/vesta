"""`walk <checkpoint> [options]`: print a part of a checkpoint's walk sheet."""
from __future__ import annotations

import os
import posixpath

from cli import args, manifest
from kernel.errors import Refusal, UsageError
from session import asides, history, review, settings, state
from steps import sheet

FLAGS = ("--short", "--here")
OPTIONS = ("--ask", "--from", "--session")
MANY = ("--paths", "--with")


def _paths(context, values):
    """(the paths in the project's own form, the lines to say about the ones that are not in it).
    A path is matched as text and need not exist; one given from the file system's root is read
    against the project root, since that is the form a harness often holds."""
    found, said = [], []
    root = os.path.realpath(context.root).replace("\\", "/").rstrip("/")
    for value in values:
        path = value.strip().replace("\\", "/")
        if not path:
            continue
        ends = path.endswith("/")
        # A leading slash is a path from the root on every system, whatever the system's own test says.
        if path.startswith("/") or os.path.isabs(path) or (len(path) > 1 and path[1] == ":"):
            full = os.path.realpath(path).replace("\\", "/")
            # Compared without regard to case where the system has none; `normcase` also turns the slashes there.
            mine, home = (os.path.normcase(each).replace("\\", "/") for each in (full, root))
            if mine != home and not mine.startswith(home + "/"):
                said.append("`%s` is not inside the project, so nothing was matched against it." % value)
                continue
            path = full[len(root):].lstrip("/")
        else:
            path = posixpath.normpath(path)
            if path == ".." or path.startswith("../"):
                said.append("`%s` is not inside the project, so nothing was matched against it." % value)
                continue
        path = "" if path == "." else path
        if path:
            found.append(path + ("/" if ends else ""))
    return found, said


def _opening(checkpoint):
    name = checkpoint.id if checkpoint.id in manifest.OPENINGS else manifest.DEFAULT_OPENING
    return manifest.member("openings", name)()


def _checked(checkpoint, options):
    """Refuse what the sheet printer would refuse, before anything is opened or changed."""
    short = "--short" in options
    if short and not checkpoint.short:
        raise UsageError("the `%s` walk has no short form; `checkpoints.%s.short` in vesta/vesta.yml names none" % (checkpoint.id, checkpoint.id))
    steps = checkpoint.short if short else checkpoint.steps
    for option in ("--from", "--with"):
        given = options.get(option, [])
        for name in ([given] if isinstance(given, str) else given):
            if name not in steps:
                raise UsageError("`%s %s` names no step of this walk; its steps are: %s" % (option, name, ", ".join(steps) or "none"))


def _aside(context, walk, forwarded):
    """What is printed in place of a walk's first part where a copy of the conversation carries it out."""
    walk.file = None
    option = forwarded + walk.session.resume
    return [
        "# Walk: %s%s" % (walk.checkpoint.id, " (short form)" if walk.short else ""), "", walk.session.heading] + walk.said + [
        "",
        "The first part of this walk is carried out aside, by a copy of this conversation: the setting `review` says so on this machine. "
        "Its sheet is not printed here.",
        "",
        "**Do:** Run `%s aside walk %s%s`. It waits for the copy for up to a minute and a half, and prints what the copy wrote and the command for "
        "the next part. Where the copy is still at work it says so: run the same command again, as often as it says. Run nothing else of Vesta's meanwhile."
        % (sheet.command_line(context), walk.checkpoint.id, option),
        "",
        "To carry the part out here instead, run `walk %s --here%s`." % (walk.checkpoint.id, option),
    ]


def run(context, arguments):
    known = context.config.checkpoints
    named = [word for word in arguments[:1] if word in known]
    if not named:
        raise UsageError("`walk` takes one checkpoint; this project has: %s" % (", ".join(known) or "none"))
    checkpoint = known[named[0]]
    opening = _opening(checkpoint)
    try:
        names, options = args.split(arguments, flags=FLAGS + tuple(opening.flags), options=OPTIONS + tuple(opening.options), many=MANY, takes=True)
    except UsageError as error:
        raise UsageError("%s. `walk %s` takes: %s" % (error, checkpoint.id, " ".join(FLAGS + tuple(opening.flags) + OPTIONS + tuple(opening.options) + MANY)))
    if len(names) != 1:
        raise UsageError("`walk` takes one checkpoint; this project has: %s" % ", ".join(known))
    _checked(checkpoint, options)
    ask = args.text(options["--ask"], context.stdin).strip() if "--ask" in options else ""
    given = {"ask": ask, "session": options.get("--session"), "from": options.get("--from"), "with": options.get("--with", [])}
    given.update((flag[2:], flag in options) for flag in opening.flags)
    given.update((option[2:], options.get(option)) for option in opening.options)
    session, said = opening.open(context, given)
    context.session = session
    paths, outside = _paths(context, options.get("--paths", []))
    asked = list(dict.fromkeys(list(options.get("--with", [])) + list(session.requested)))
    walk = sheet.Walk(checkpoint, session, paths, ask, requested=asked, short="--short" in options)
    walk.said = said + outside
    walk.matched = opening.paths(context, session, walk.paths)
    mine = checkpoint.id in context.known.get("walks-aside", ()) and session.status == state.OPEN
    first = mine and "--from" not in options
    copy = state.copy_of(session) if mine else None
    inside = bool(context.environ.get(asides.TOKEN))
    if copy is not None and not inside:
        # While a copy holds the first part, no step of that part is printed here: its notes would be written twice.
        following = sheet.following(context, walk)
        names = checkpoint.short if "--short" in options else checkpoint.steps
        start = options.get("--from")
        later = following is not None and following.id in names and start in names and names.index(start) >= names.index(following.id)
        if ("--here" in options or "--from" in options) and not later:
            raise Refusal(
                "a copy of the conversation is carrying the first part of this walk out for %s, started %s; carrying it out here as well would write "
                "its notes twice. `aside walk %s%s` waits for the copy; `aside walk %s --stop%s` ends it, and this command then prints the part."
                % (session.id, copy["started"], checkpoint.id, session.resume, checkpoint.id, session.resume), settings.RULE)
    aside = first and "--here" not in options and not inside and (copy is not None or review.in_effect(context) == review.ASIDE)
    forwarded = (" --short" if "--short" in options else "") + "".join(
        " %s %s" % (name, " ".join(history.quoted(value) for value in options[name])) for name in MANY if options.get(name))
    for line in (_aside(context, walk, forwarded) if aside else sheet.render(context, walk, options.get("--from"))):
        context.write(line)
    return 0
