"""`show <id>…`: print records in full. It records nothing."""
from __future__ import annotations

from cli import args
from kernel import ids
from kernel.errors import UsageError


def resolve(context, name):
    """The (store, record) a label, an internal id or a joined reference names. Raises UsageError."""
    found = context.stores.resolve(name) if name.strip() else None
    if found is None:
        label = ids.parse_ref(name)[0] or name
        for store in context.stores.all():
            for path in store.unread():
                if path.endswith("/" + label + ".md"):
                    raise UsageError("%s is there and does not read; `check` says what is wrong with it" % path)
        if context.stores.unreadable:
            raise UsageError("`%s` names no record that reads; the store %s cannot be read, and `check` says why" % (name, ", ".join(sorted(context.stores.unreadable))))
        raise UsageError("`%s` names no record; `index --all` lists the records" % name)
    return found


def print_record(context, record):
    context.write("<!-- %s -->" % record.path)
    context.write(context.tree.read(record.path).rstrip("\n"))
    context.write()


def run(context, arguments):
    names, _ = args.split(arguments, takes=True)
    if not names:
        raise UsageError("`show` takes one or more record ids, as `show D-004`")
    for store, record in [resolve(context, name) for name in names]:
        print_record(context, record)
    return 0
