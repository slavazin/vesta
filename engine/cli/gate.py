"""The gate every lasting change passes: the checks run over the project as it would be, and the
change is written only where it brings no finding the project does not have now."""
from __future__ import annotations

import re

from cli import build, handedits
from cli.commands import check
from kernel.errors import Refusal
from kernel.finding import ERROR
from proposals import admitted, decide, proposal as proposals
from session import pending

RULE = "vesta/INTERNALS.md, How changes are made"


def _key(finding, reword=None):
    file, message = finding.file, finding.message
    if reword is not None:
        file, message = reword(file), reword(message)
    return (finding.severity, finding.check, file, message)


def _unedited(context, overlay, what, settling=False):
    """Refuse a change that would write over a governed file edited by hand since its last approval:
    the edit would pass as approved along with the change."""
    waiting = [] if settling else handedits.unaccepted(context)
    if waiting:
        raise Refusal(
            "%s cannot be done while %s changed by hand and not accepted: the folder is read by %s. Accept %s with `adopt <path>` once the "
            "owner has seen it, or put it back as it was. Nothing was changed."
            % (what, ", ".join(waiting) + (" is" if len(waiting) == 1 else " are"), "it" if len(waiting) == 1 else "them", "it" if len(waiting) == 1 else "each"),
            RULE,
        )
    recorded = admitted.read(context.tree)
    governed = set(admitted.governed_paths(context.tree, context.config, context.stores))
    edited = [
        path for path in overlay.changed()
        if path in governed and context.tree.is_file(path) and recorded.get(path) != admitted.digest(context.tree.read(path))
    ]
    if edited:
        raise Refusal(
            "%s would write over %s, which %s changed by hand since %s last approved, so the hand edit would pass as approved. "
            "Settle that first: accept the file as it stands with `adopt <path>` once the owner has seen it, "
            "or put it back as it was. Nothing was changed."
            % (what, ", ".join(edited), "was" if len(edited) == 1 else "were", "it was" if len(edited) == 1 else "they were"),
            RULE,
        )


def commit(context, overlay, what, renamed=None, cause=None, settling=False):
    """Refresh the fingerprints for what the overlay changes, run the checks before and after, and
    commit. Raises Refusal, writing nothing, where a new error appears. Returns the paths written.

    The change being made is the one that stands: a waiting proposal it leaves unable to be applied
    is closed as stale in the same commit, naming `cause` as what overtook it."""
    _unedited(context, overlay, what, settling)
    reword = None
    if renamed:
        word = re.compile(r"(?<![\w-])(%s)(?![\w-])" % "|".join(re.escape(label) for label in sorted(renamed, key=len, reverse=True)))
        reword = lambda text: word.sub(lambda match: renamed[match.group(1)], text)  # noqa: E731
    before = set(_key(finding, reword) for finding in check.findings(context)[0])
    while True:
        after = build.context(context.root, context.out, context.clock, overlay)
        decide.rehash(overlay, after.config, after.stores)
        after = build.context(context.root, context.out, context.clock, overlay)
        fresh = [finding for finding in check.findings(after)[0] if _key(finding) not in before]
        errors = [finding for finding in fresh if finding.severity == ERROR]
        losers = []
        for store, record in pending.pending(after):
            reason = proposals.overtaken(after, proposals.Proposal(store, record))
            if reason:
                losers.append((store, record, reason))
        if not losers:
            break
        for store, record, reason in losers:
            decide.overtake(overlay, after, proposals.Proposal(store, record), cause or what[:1].lower() + what[1:])
            context.write(
                "Note: %s can no longer be applied (%s). This change stands, and %s is closed as stale in %s/; "
                "draft it again if it is still wanted." % (record.label, reason, record.label, proposals.LOG)
            )
    waiting = dict((record.path, record.label) for _, record in pending.pending(after))
    for finding in errors:
        if finding.file in waiting:
            context.write(
                "Note: after this change %s needs correcting before it can be applied: %s. `proposals %s` says more."
                % (waiting[finding.file], finding.message, waiting[finding.file])
            )
    errors = [finding for finding in errors if finding.file not in waiting]
    for finding in fresh:
        if finding.severity != ERROR:
            context.write("Note, a new warning: %s" % finding.render())
    if errors:
        raise Refusal(
            "%s would leave the project with %d error%s it does not have now:\n%s\nNothing was changed."
            % (what, len(errors), "" if len(errors) == 1 else "s", "\n".join("- " + finding.render() for finding in errors)),
            RULE,
        )
    return overlay.commit()
