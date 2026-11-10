"""`scopes <path>…`: the records whose paths cover each given path."""
from __future__ import annotations

from cli import args
from kernel.errors import UsageError
from matchers import scope


def run(context, arguments):
    paths, _ = args.split(arguments, takes=True)
    if not paths:
        raise UsageError("`scopes` takes one or more paths, as `scopes src/http/client.py`")
    context.write("# Records that govern each path")
    context.write()
    for path in paths:
        if not [part for part in path.replace("\\", "/").split("/") if part not in ("", ".")]:
            raise UsageError("`%s` names the whole project; give a path inside it" % path)
        labels = []
        for store in context.stores.all():
            labels.extend(record.label for record in scope.matching(store, [path]))
        context.write("- `%s`: %s" % (path, ", ".join(labels) if labels else "none"))
    context.write()
    context.write("A record that declares no paths is never listed here; the index is where it is found.")
    return 0
