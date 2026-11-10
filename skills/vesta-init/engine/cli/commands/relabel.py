"""`relabel <store> [--one <id>]`: rename a store's records to its configured label form, or move
one record to the next free number."""
from __future__ import annotations

from cli import args, gate
from kernel import tree as trees
from kernel.errors import UsageError
from model.abstractions import Change, KindError
from proposals import relabel

# The command builds its change from what it reads, so it runs alone (cli/main.py).
ALONE = True


def run(context, arguments):
    names, options = args.split(arguments, options=("--one",), takes=True)
    store = context.stores.get(names[0]) if len(names) == 1 else None
    if store is None:
        raise UsageError("`relabel` takes one store, as `relabel decisions`; the stores are: %s" % ", ".join(context.stores.names()))
    only = None
    if "--one" in options:
        only = store.get(options["--one"])
        if only is None:
            raise UsageError("`%s` names no record of the store `%s`" % (options["--one"], store.name))
    change = Change(store.name)
    try:
        renamed = relabel.plan(context, store, store.settings.prefix, store.settings.digits, only)
        relabel.into(change, context, renamed)
    except KindError as error:
        raise UsageError(str(error))
    if not renamed:
        context.write("Every record of `%s` already has the label form the configuration gives. Nothing was changed." % store.name)
        return 0
    overlay = trees.Overlay(context.tree)
    for source, target in change.moves:
        overlay.move(source, target)
    for path, text in change.writes.items():
        overlay.write(path, text)
    written = gate.commit(context, overlay, "Renaming", change.renamed)
    context.write("Renamed %d record%s of `%s`: %s." % (len(renamed), "" if len(renamed) == 1 else "s", store.name, ", ".join("%s to %s" % (record.label, new) for record, new in renamed)))
    context.write("Every reference and mention follows. %d files were written." % len(written))
    return 0
