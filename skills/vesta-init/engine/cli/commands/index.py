"""`index [--store <name>] [--all]`: the index of the recalled stores."""
from __future__ import annotations

from cli import args
from kernel.errors import UsageError
from matchers import index


def run(context, arguments):
    _, options = args.split(arguments, flags=("--all",), options=("--store",))
    stores = context.stores.recalled()
    if "--store" in options:
        name = options["--store"]
        store = context.stores.get(name)
        if name in context.stores.unreadable:
            raise UsageError("the store `%s` cannot be read; `check` says why" % name)
        if store is None or store not in stores:
            raise UsageError("`%s` is not a store that has an index; those are: %s" % (name, ", ".join(s.name for s in stores) or "none"))
        stores = [store]
    context.write("# Index")
    for store in stores:
        context.write()
        context.write("## %s" % store.name)
        blocks = index.project(store, everything="--all" in options, triggers=True)
        context.write()
        if not blocks:
            context.write("none")
            continue
        context.write("```")
        for position, block in enumerate(blocks):
            if position:
                context.write()
            for line in block:
                context.write(line)
        context.write("```")
    unread = [path for store in stores for path in store.unread()]
    lost = sorted(name for name in context.stores.unreadable if context.config.stores[name].recall == "index")
    if unread or lost:
        context.write()
        context.write("**Not everything is listed.** `check` says what is wrong with each:")
        for name in lost:
            context.write("- the store `%s` cannot be read, so none of its records is here" % name)
        for path in unread:
            context.write("- %s does not read" % path)
    context.write()
    context.write("Each block says when to open a record, never what it decides. Read a record with `show <id>` before acting on it.")
    context.write()
    context.write(index.RESIDUE)
    return 0
