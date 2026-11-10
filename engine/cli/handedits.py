"""Hand edits: a file under vesta/ changed outside the engine is logged where a command meets it.

A decision, a walk file or the writing rules may be edited by hand; the log then says so, and a
waiting proposal on the same file is closed as stale, since the edit was made first. The schemas and
the configuration are what every command reads the folder by, so a hand edit to one of those is not
logged here: every command says it is not accepted, and nothing is applied until `adopt` accepts it.
"""
from __future__ import annotations

from cli import build
from kernel import ids
from kernel import tree as trees
from kernel.errors import Refusal, UsageError
from model import config as configuration
from proposals import admitted, decide, proposal as proposals
from session import pending
from stores import admissions

CHANGED, WRITTEN, REMOVED = "changed by hand", "written by hand", "removed by hand"


def strict(path):
    """Say whether a governed file is one a hand edit may not pass: a schema, or the configuration."""
    return path == configuration.PATH or path.endswith("/" + admitted.SCHEMA)


def _read(context):
    """(the recorded fingerprints, the fingerprints as the files stand), or None where they do not read."""
    try:
        if not context.tree.is_file(admitted.PATH):
            return None
        return admitted.read(context.tree), admitted.current(context.tree, context.config, context.stores)
    except (OSError, ValueError, UnicodeDecodeError):
        return None


def unaccepted(context):
    """The schemas and the configuration that were changed by hand and not accepted since."""
    read = _read(context)
    if read is None:
        return []
    recorded, current = read
    return sorted(path for path, digest in current.items() if strict(path) and recorded.get(path) != digest)


def _edits(context):
    """([(path, what was done to it)], the fingerprints brought up to date) for the files a hand edit may pass in."""
    read = _read(context)
    if read is None:
        return [], {}
    recorded, current = read
    found = []
    for path, digest in sorted(current.items()):
        if not strict(path) and recorded.get(path) != digest:
            found.append((path, CHANGED if path in recorded else WRITTEN))
            recorded[path] = digest
    for path in sorted(set(recorded) - set(current)):
        if not strict(path) and not context.tree.is_file(path):
            found.append((path, REMOVED))
            del recorded[path]
    return found, recorded


def _touches(context, proposal, paths):
    """The first of those paths a waiting proposal's target names, or None."""
    for name in str(proposal.target).split(","):
        name = name.strip()
        named = context.stores.resolve(name) or context.stores.resolve(ids.split_trigger_ref(name)[0] or name)
        if named is not None and named[1].path in paths:
            return named[1].path
        if trees.HOME + name in paths:
            return trees.HOME + name
    return None


def _log(context):
    found, recorded = _edits(context)
    if not found:
        return []
    tree = context.tree
    overlay = trees.Overlay(tree)
    text = tree.read_or(admissions.PATH)
    text += "" if not text or text.endswith("\n") else "\n"
    overlay.write(admissions.PATH, text + "".join(admissions.edited(context.clock.today(), path, what) for path, what in found))
    overlay.write(admitted.PATH, admitted.text(recorded))
    lines = ["Note: %s was %s; %s now says so. Tell the owner." % (path, what, admissions.PATH) for path, what in found]
    # The edit was made first, so it stands: a waiting proposal on the same file is closed as stale.
    changed = set(path for path, what in found if what != WRITTEN)
    for store, record in pending.pending(context):
        proposal = proposals.Proposal(store, record)
        path = _touches(context, proposal, changed)
        reason = proposals.overtaken(context, proposal)
        if path is None and not reason:
            continue
        decide.overtake(overlay, context, proposal, "a hand edit to %s" % path if path else "a hand edit")
        lines.append(
            "Note: %s was waiting to change %s; the hand edit stands, and %s is closed as stale in %s/. Draft it again if it is still wanted."
            % (record.label, path or "what a hand edit removed", record.label, proposals.LOG)
        )
    overlay.commit()
    return lines


def log(context, locked=False):
    """Log every hand edit to a file that is not strict, bring its fingerprint up to date, and say
    which strict files wait to be accepted. Returns the lines to print. Logging is skipped, for the
    next command to do, where another command is changing the folder or the log cannot be written."""
    lines = []
    try:
        if _edits(context)[0]:
            if locked:
                lines = _log(context)
            else:
                with context.tree.lock(trees.COMMAND_LOCK) as held:
                    if held:
                        lines = _log(build.context(context.root, context.out, context.clock))
                        # The engine wrote these, in this command: no session reports them as its own change.
                        getattr(context.tree, "written", []).extend([admissions.PATH, admitted.PATH])
    except (OSError, ValueError, UsageError, Refusal):
        lines = []
    for path in unaccepted(context):
        lines.append(
            "Note: %s was changed by hand and is not accepted. Until `adopt %s`, no proposal is applied. Tell the owner."
            % (path, path)
        )
    return lines
