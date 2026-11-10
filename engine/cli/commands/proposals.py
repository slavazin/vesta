"""`proposals [<id>]`: the proposals waiting for the owner; with an id, one of them in full, with
what is still wrong with it as drafted."""
from __future__ import annotations

from cli import args
from cli.commands import propose
from kernel import ids
from kernel.errors import UsageError
from proposals import proposal as proposals
from session import pending


def run(context, arguments):
    names, _ = args.split(arguments, takes=True)
    if len(names) > 1:
        raise UsageError("`proposals` takes no argument, or the id of one proposal")
    if not names:
        lines = pending.lines(context)
        context.write("# Proposals waiting: %d" % len(lines))
        context.write()
        for line in lines or ["none"]:
            context.write(line)
        if lines:
            context.write()
            context.write("`proposals <id>` prints one in full. The owner decides each by its id; `apply` and `reject` record the decision.")
        return 0
    label = ids.parse_ref(names[0])[0] or names[0]
    logged = "%s/%s.md" % (proposals.LOG, label)
    if context.tree.is_file(logged) and all(store.get(names[0]) is None for store in pending.stores_of(context)):
        context.write("<!-- %s: decided, and kept as it was decided -->" % logged)
        context.write(context.tree.read(logged).rstrip("\n"))
        return 0
    proposal = proposals.find(context, names[0])
    context.write("<!-- %s -->" % proposal.record.path)
    context.write(context.tree.read(proposal.record.path).rstrip("\n"))
    draft = ""
    if context.tree.is_file(proposal.draft_path):
        draft = context.tree.read(proposal.draft_path)
        context.write()
        context.write("<!-- %s -->" % proposal.draft_path)
        context.write(draft.rstrip("\n"))
    context.write()
    found = proposals.problems(context, proposal)
    context.write("## As drafted")
    context.write()
    if found:
        context.write("It cannot be applied yet:")
        for line in found:
            context.write("- %s" % line)
    else:
        context.write("It reads, and could be applied once the owner approves it.")
    if draft and proposal.kind in context.known.get(proposals.TABLE, ()) and proposal.kind in context.config.kinds:
        kind = context.member(proposals.TABLE, proposal.kind)()
        for line in propose.covered(context, kind, proposal.target, draft, proposal.draft_path):
            context.write(line)
    return 0
