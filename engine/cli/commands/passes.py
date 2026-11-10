"""`pass seal [--hold <id>,…] [--note <file or ->]`: end the open learn pass."""
from __future__ import annotations

from cli import args
from kernel import tree as trees
from kernel.errors import UsageError
from session import passes

ACTS = ("seal",)

# The command builds its change from what it reads, so it runs alone (cli/main.py).
ALONE = True


def _note(context, value):
    if value == "-":
        return args.read_stdin(context.stdin)
    try:
        return context.tree.read(trees.clean(value))
    except (OSError, ValueError, UnicodeDecodeError):
        raise UsageError("`--note %s` is not a text file of this project; give its path from the project root, or `-` to send the text on standard input" % value)


def run(context, arguments):
    words, options = args.split(arguments, options=("--hold", "--note"), takes=True)
    if words != ["seal"]:
        raise UsageError("`pass` takes: seal [--hold <id>,…] [--note <file or ->]")
    found = passes.current(context.tree, "`pass seal`")
    hold = [name.strip() for name in options.get("--hold", "").split(",") if name.strip()]
    path, held, archived = passes.seal(context, found, hold, _note(context, options["--note"]) if "--note" in options else "")
    context.write("%s is sealed. Its note is %s:" % (found.id, path))
    context.write()
    for line in context.tree.read(path).rstrip("\n").split("\n"):
        context.write(line)
    context.write()
    context.write("Archived as read: %d. Kept open for a later pass: %d." % (len(archived), len(held)))
    return 0
