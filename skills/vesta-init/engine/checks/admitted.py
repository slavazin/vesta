"""The `admitted` check: every governed file is as it was last approved, every record of a governed
store entered through an approval. Where a row or a lens came from is read by the `walks` check."""
from __future__ import annotations

from kernel.finding import ERROR, Finding
from model.abstractions import Check
from proposals import admitted
from stores import admissions

WAYS = (
    "Accept it as it stands with `adopt %s`, once the owner has seen it, "
    "or put it back as it was and make the change through `propose`"
)


class AdmittedCheck(Check):
    id = "admitted"
    residue = "not who typed the approver's name; not a fingerprint file or an admissions log edited by hand to match a file"

    def run(self, context):
        found = []
        tree = context.tree
        recorded = admitted.read(tree)
        current = admitted.current(tree, context.config, context.stores)
        for path, digest in sorted(current.items()):
            if path not in recorded:
                found.append(Finding(ERROR, self.id, path, 1, "the file was written without an approval. " + WAYS % path))
            elif recorded[path] != digest:
                found.append(Finding(ERROR, self.id, path, 1, "the file was changed by hand since it was last approved. " + WAYS % path))
        for path in sorted(set(recorded) - set(current)):
            found.append(Finding(ERROR, self.id, admitted.PATH, 1, "%s is recorded as approved and is no longer there. Put it back, or accept that it is gone with `adopt %s` once the owner has agreed" % (path, path)))
        uids, paths = admissions.approved_subjects(tree)
        for store in context.stores.all():
            if not store.settings.governed:
                continue
            for record in store.list():
                if record.uid not in uids and record.path not in paths and record.path in recorded:
                    found.append(Finding(ERROR, self.id, record.path, 1, "no line of %s approves this record. " % admissions.PATH + WAYS % record.path))
        return found


MEMBER = AdmittedCheck
