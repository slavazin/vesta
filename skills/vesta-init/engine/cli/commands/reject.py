"""`reject <P-id> --reason <text or -> [--ref <commit or note>] [--by "<name>"]`: record that the
owner turned a proposal down."""
from __future__ import annotations

from cli import args, gate
from cli.commands import apply
from kernel.errors import Refusal, UsageError
from proposals import decide, proposal as proposals
from stores import admissions

# The command builds its change from what it reads, so it runs alone (cli/main.py).
ALONE = True


def run(context, arguments):
    names, options = args.split(arguments, options=("--by", "--reason", apply.REF), takes=True)
    if len(names) != 1:
        raise UsageError("`reject` takes the id of one proposal, as `reject P-007 --reason -`")
    proposal = proposals.find(context, names[0])
    name, reference = apply.decided_by(context, options, "--by")
    reason = args.text(options["--reason"], context.stdin).strip() if "--reason" in options else ""
    if not reason:
        raise Refusal("`--reason` is missing, so nothing was changed. A rejection says why, in the owner's words: a later proposal of the same shape is shown with it.", gate.RULE)
    if admissions.decided(context.tree, proposal.record.uid):
        raise Refusal("%s already has a line in %s: it was decided before. Nothing was changed." % (proposal.label, admissions.PATH), gate.RULE)
    overlay = decide.reject(context, proposal, name, reason, reference)
    gate.commit(context, overlay, "Rejecting %s" % proposal.label, cause=proposal.label)
    context.write("Rejected %s%s: %s" % (proposal.label, ", by %s" % name if name else "", " ".join(reason.split())))
    if proposal.evidence:
        context.write("Its %d observation%s went to the archive as dropped." % (len(proposal.evidence), "" if len(proposal.evidence) == 1 else "s"))
    context.write("The proposal is now in %s/." % proposals.LOG)
    return 0
