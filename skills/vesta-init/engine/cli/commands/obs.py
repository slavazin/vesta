"""`obs add`, `obs list` and `obs dispose`: write a session's observations, print the ones a learn
pass reads, or set aside one a pass found to be noise."""
from __future__ import annotations

from cli import args, sessions
from kernel.errors import Refusal, UsageError
from session import observations, passes, state
from stores.filestore import ARCHIVE

ACTS = ("add", "list", "dispose")
STORE = "--store"

# The command builds its change from what it reads, so it runs alone (cli/main.py).
ALONE = True


def _add(context, store, options):
    text = args.read_stdin(context.stdin)
    if not text.strip():
        raise UsageError("`obs add` reads a JSON array of items from standard input, and standard input was empty. Each item is %s" % observations.shape(store))
    observations.usable(store)
    session, opened = sessions.current_or_late(context, options)
    if session.status != state.OPEN:
        raise Refusal("%s is %s; an observation goes into an open session. Run `obs add` without `--session`, and one is opened to hold it." % (session.id, session.status), state.RULE)
    records = observations.add(context, store, session, text)
    context.session = state.update(context.tree, session, lambda fresh: observations.note(fresh, store, records))
    if opened:
        context.write("No session was open, so %s was opened late to hold what was written." % session.id)
    context.write("Written to %s/open/, for %s: %d observation%s." % (store.path, session.id, len(records), "" if len(records) == 1 else "s"))
    for record in records:
        context.write("- %s (%s) %s" % (record.label, record.get(observations.VIA), store.title(record)))
    return 0


def _list(context, store, options):
    if "--open" in options and "--pass" in options:
        raise UsageError("`obs list` takes `--open` or `--pass <n>`, not both")
    if "--pass" in options:
        if not options["--pass"].isdigit():
            raise UsageError("`--pass` takes the number of a learn pass, as `obs list --pass 2`")
        records = observations.listed(store, ARCHIVE, int(options["--pass"]))
        what = "archived by pass %d" % int(options["--pass"])
    else:
        records = observations.listed(store)
        what = "open"
    context.write("# Observations of `%s`, %s: %d" % (store.name, what, len(records)))
    for record in records:
        context.write()
        for line in observations.form(store, record):
            context.write(line)
    unread = store.unread()
    if unread:
        context.write()
        context.write("**Not everything is listed.** These do not read, and `check` says why: %s." % ", ".join(unread))
    return 0


def _dispose(context, words, options):
    if len(words) != 2 or "--as" not in options:
        raise UsageError("`obs dispose` takes one note and what became of it, as `obs dispose <id> --as \"dropped — <reason>\"`; `--as -` reads the text from standard input")
    found = passes.current(context.tree, "`obs dispose`")
    record, text = passes.dispose(context, found, words[1], args.text(options["--as"], context.stdin))
    context.write("%s is set aside as `%s` and archived under %s." % (record.label, text, found.id))
    return 0


def run(context, arguments):
    words, options = args.split(arguments, flags=("--open",), options=("--pass", "--as", STORE, sessions.OPTION), takes=True)
    if not words or words[0] not in ACTS:
        raise UsageError("`obs` takes one of: %s" % ", ".join(ACTS))
    if words[0] == "dispose":
        return _dispose(context, words, options)
    if len(words) != 1:
        raise UsageError("`obs %s` takes no `%s`" % (words[0], words[1]))
    store = observations.store_of(context, options.get(STORE))
    return _add(context, store, options) if words[0] == "add" else _list(context, store, options)
