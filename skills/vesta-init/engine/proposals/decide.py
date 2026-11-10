"""Deciding a proposal: the target's change, and everything that goes with it, built in one overlay.

The command line then runs the checks over the overlay and commits it, so a decision lands wholly
or not at all.
"""
from __future__ import annotations

import re

from kernel import ids, markdown
from kernel import tree as trees
from model.abstractions import DISPOSITION, OPEN, OUTCOME
from proposals import admitted, proposal as proposals
from session import passes
from stores import admissions

# What a new record's approver field holds where neither a name nor a reference was given.
NAMELESS = "the owner"


def _who(word, name):
    name = " ".join(str(name).split())
    return "%s by %s" % (word, name) if name else word


def overtake(overlay, context, proposal, cause):
    """Close a waiting proposal that a change made first left unable to be applied: it goes to the
    log as stale, with a line saying what overtook it. Its evidence stays as it is."""
    today = context.clock.today()
    _close(overlay, context, proposal, "stale, %s: overtaken by %s" % (today, cause))
    line = admissions.overtaken(today, proposal.ref, proposal.kind, proposal.target, cause)
    overlay.write(admissions.PATH, admissions.with_line(overlay, line))


def _dispose(overlay, context, proposal, text):
    folder = passes.archive_folder(context.tree)
    for store, record in proposals.evidence_records(context, proposal.evidence)[0]:
        if store.type.life(record, DISPOSITION) != OPEN:
            continue  # dealt with already, by a pass or by another proposal: what it says stands
        changed = record.copy()
        changed.fields[store.type.life_field(DISPOSITION)] = text
        target = store.path_for(record.label, folder)
        overlay.move(record.path, target)
        overlay.write(target, store.text(changed))


def _close(overlay, context, proposal, outcome, replaced=()):
    """The proposal with its outcome, and what it replaced, moved to the log with its draft."""
    store, record = proposal.store, proposal.record.copy()
    record.fields[store.type.life_field(OUTCOME)] = outcome
    if replaced:
        body = record.body.rstrip("\n") + "\n\n## %s\n" % proposals.REPLACED
        for what, old in replaced:
            fence = "`" * max(4, 1 + max([len(run) for run in _runs(old)] + [0]))
            body += "\n%s:\n\n%s\n%s\n%s\n" % (what, fence, old, fence)
        record.body = body
    target = "%s/%s.md" % (proposals.LOG, record.label)
    overlay.move(record.path, target)
    overlay.write(target, store.text(record))
    if context.tree.is_file(proposal.draft_path):
        overlay.move(proposal.draft_path, "%s/%s%s" % (proposals.LOG, record.label, proposals.DRAFT))


def _runs(text):
    return re.findall(r"`+", text)


def approve(context, proposal, kind, approver, reference=""):
    """(the overlay holding an approved proposal's whole effect, the Change its kind made)."""
    change = kind.changes(proposal, context, approver or reference or NAMELESS)
    overlay = trees.Overlay(context.tree)
    for source, target in change.moves:
        overlay.move(source, target)
    for path, text in change.writes.items():
        overlay.write(path, text)
    label = ids.parse_ref(change.subject)[0] if ids.parse_ref(change.subject)[1] else change.subject
    today = context.clock.today()
    _dispose(overlay, context, proposal, "%s → %s (%s)" % ("promoted" if change.created else "folded", label, proposal.label))
    _close(overlay, context, proposal, "%s, %s" % (_who("approved", approver), today), change.replaced)
    line = admissions.approved(today, proposal.ref, proposal.kind, change.subject, approver, len(proposal.evidence), reference)
    overlay.write(admissions.PATH, admissions.with_line(overlay, line))
    return overlay, change


def reject(context, proposal, name, reason, reference=""):
    """The overlay holding a rejected proposal's whole effect."""
    overlay = trees.Overlay(context.tree)
    today = context.clock.today()
    reason = " ".join(reason.split())
    _dispose(overlay, context, proposal, "dropped — rejected (%s): %s" % (proposal.label, reason))
    _close(overlay, context, proposal, "%s, %s: %s" % (_who("rejected", name), today, reason))
    line = admissions.rejected(today, proposal.ref, proposal.kind, proposal.target, name, reason, reference)
    overlay.write(admissions.PATH, admissions.with_line(overlay, line))
    return overlay


def rehash(overlay, config, stores):
    """Bring the admitted-hash file in line with what the overlay changes: a governed file it
    writes gets its new fingerprint, and a file it removes is dropped."""
    governed = set(admitted.governed_paths(overlay, config, stores))
    hashes = admitted.read(overlay)
    for path in overlay.changed():
        if path in governed:
            hashes[path] = admitted.digest(overlay.read(path))
        else:
            hashes.pop(path, None)
    overlay.write(admitted.PATH, admitted.text(hashes))
