"""`apply <P-id> [--ref <commit or note>] [--approved-by "<name>"]`: make an approved proposal's
change, wholly or not at all. Running it is the record that the owner approved; the reference and
the name are bookkeeping."""
from __future__ import annotations

from cli import args, gate
from kernel import ids
from kernel.errors import Refusal, UsageError
from model.abstractions import KindError
from proposals import decide, proposal as proposals
from stores import admissions

# The command builds its change from what it reads, so it runs alone (cli/main.py).
ALONE = True


REF = "--ref"
NAMELESS = "the owner"


def decided_by(context, options, flag):
    """(the name to record, the reference to record), both bookkeeping and either may be empty.
    The name is the one given, else the owner's name on record; `-` reads either from standard input."""
    name = " ".join(args.text(str(options.get(flag, "")), context.stdin).split()) if flag in options else ""
    reference = " ".join(args.text(str(options.get(REF, "")), context.stdin).split()) if REF in options else ""
    return (name if name not in ("", "-") else context.config.owner), ("" if reference == "-" else reference)


def run(context, arguments):
    names, options = args.split(arguments, options=("--approved-by", REF), takes=True)
    if len(names) != 1:
        raise UsageError("`apply` takes the id of one proposal, as `apply P-007`; `--ref <commit or note>` and `--approved-by \"<name>\"` add to the record")
    proposal = proposals.find(context, names[0])
    approver, reference = decided_by(context, options, "--approved-by")
    if admissions.decided(context.tree, proposal.record.uid):
        raise Refusal("%s already has a line in %s: it was decided before. Nothing was changed." % (proposal.label, admissions.PATH), gate.RULE)
    kind = proposals.kind_of(context, proposal.kind)
    proposals.checked(context, proposal)
    try:
        overlay, change = decide.approve(context, proposal, kind, approver, reference)
    except KindError as error:
        raise Refusal("%s cannot be applied: %s. Nothing was changed." % (proposal.label, error), proposals.RULE % proposal.store.path)
    written = gate.commit(context, overlay, "Applying %s" % proposal.label, change.renamed, cause=proposal.label)
    label, uid = ids.parse_ref(change.subject)
    context.write("Applied %s%s: %s %s." % (proposal.label, ", approved by %s" % approver if approver else "", proposal.kind, label if uid else change.subject))
    if change.created:
        context.write("The new record is %s." % label)
    if change.renamed:
        context.write("Renamed: %s." % ", ".join("%s to %s" % pair for pair in sorted(change.renamed.items())))
    if proposal.evidence:
        context.write("Its %d observation%s went to the archive." % (len(proposal.evidence), "" if len(proposal.evidence) == 1 else "s"))
    context.write("The proposal is now in %s/. %d files were written." % (proposals.LOG, len(written)))
    return 0
