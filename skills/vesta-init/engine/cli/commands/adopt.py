"""`adopt <path> [--reason <text or ->] [--ref <commit or note>] [--approved-by "<name>"]`: accept a
file as it stands after a hand edit to the configuration or a schema."""
from __future__ import annotations

from cli import args, gate
from cli.commands import apply
from kernel import tree as trees
from kernel.errors import UsageError
from proposals import admitted
from stores import admissions

REASON = "edited by hand"
GONE = "removed by hand"

# The command builds its change from what it reads, so it runs alone (cli/main.py).
ALONE = True


def run(context, arguments):
    names, options = args.split(arguments, options=("--approved-by", "--reason", apply.REF), takes=True)
    if len(names) != 1:
        raise UsageError("`adopt` takes one file, as `adopt vesta/vesta.yml`")
    governed = admitted.governed_paths(context.tree, context.config, context.stores)
    text = names[0].replace("\\", "/")
    root = context.root.replace("\\", "/").rstrip("/") + "/"
    text = text[len(root):] if text.startswith(root) else text
    path = text if text.startswith(trees.HOME) else trees.HOME + text
    recorded = admitted.read(context.tree)
    if path not in governed and path in recorded and not context.tree.is_file(path):
        approver, reference = apply.decided_by(context, options, "--approved-by")
        reason = args.text(options["--reason"], context.stdin).strip() if "--reason" in options else GONE
        overlay = trees.Overlay(context.tree)
        del recorded[path]
        overlay.write(admitted.PATH, admitted.text(recorded))
        overlay.write(admissions.PATH, admissions.with_line(context.tree, admissions.adopted(context.clock.today(), path, approver, reason or GONE, reference)))
        gate.commit(context, overlay, "Accepting that %s is gone" % path, settling=True)
        context.write("Accepted that %s is gone. A line went to %s." % (path, admissions.PATH))
        return 0
    if path not in governed:
        raise UsageError("`%s` is not a file that needs approval. Those are the records of the governed stores, the walk files, vesta/language.md, vesta/vesta.yml and each SCHEMA.md." % names[0])
    approver, reference = apply.decided_by(context, options, "--approved-by")
    reason = args.text(options["--reason"], context.stdin).strip() if "--reason" in options else REASON
    if admitted.read(context.tree).get(path) == admitted.digest(context.tree.read(path)):
        context.write("%s is as it was last approved. Nothing was changed." % path)
        return 0
    overlay = trees.Overlay(context.tree)
    hashes = admitted.read(context.tree)
    hashes[path] = admitted.digest(context.tree.read(path))
    overlay.write(admitted.PATH, admitted.text(hashes))
    overlay.write(admissions.PATH, admissions.with_line(context.tree, admissions.adopted(context.clock.today(), path, approver, reason or REASON, reference)))
    gate.commit(context, overlay, "Accepting %s as it stands" % path, settling=True)
    context.write("Accepted %s as it stands. A line went to %s." % (path, admissions.PATH))
    return 0
