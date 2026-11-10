"""The admissions log: one line for each decided proposal and each file accepted as it stands."""
from __future__ import annotations

import re

PATH = "vesta/log/admissions.md"
SEP = " · "
APPROVED, REJECTED, ADOPT, EDIT, STALE = "approved", "rejected", "adopt", "edit", "stale"
ID = re.compile(r"@([0-9a-f]{8})\b")


def _flat(text):
    return " ".join(str(text).split())


def _who(word, name):
    """`approved`, or `approved by <name>` where a name was given: the name is bookkeeping."""
    return "%s by %s" % (word, _flat(name)) if _flat(name) else word


def _line(parts, reference=""):
    return "- " + SEP.join(parts + (["ref %s" % _flat(reference)] if _flat(reference) else [])) + "\n"


def approved(date, proposal_ref, kind, subject, name, evidence, reference=""):
    return _line([date, proposal_ref, kind, subject, _who(APPROVED, name), "evidence %d" % evidence], reference)


def rejected(date, proposal_ref, kind, subject, name, reason, reference=""):
    return _line([date, proposal_ref, kind, subject, "%s — %s" % (_who(REJECTED, name), _flat(reason))], reference)


def overtaken(date, proposal_ref, kind, subject, cause):
    """The line for a waiting proposal that a change made first left unable to be applied."""
    return _line([date, proposal_ref, kind, subject, "%s — overtaken by %s" % (STALE, _flat(cause))])


def adopted(date, path, name, reason, reference=""):
    return _line([date, ADOPT, path, "%s — %s" % (_who(APPROVED, name), _flat(reason))], reference)


def edited(date, path, what):
    """The line for a file changed by hand, which the engine logs where it meets it."""
    return _line([date, EDIT, path, _flat(what)])


def lines(tree):
    """Every line of the log that is an entry, as its list of parts."""
    found = []
    for line in tree.read_or(PATH).split("\n"):
        if line.startswith("- "):
            found.append([part.strip() for part in line[2:].split(SEP)])
    return found


def with_line(tree, line):
    """The log's text with one line appended."""
    text = tree.read_or(PATH)
    if text and not text.endswith("\n"):
        text += "\n"
    return text + line


def decided(tree, uid):
    """Say whether the log already holds a decision on the proposal of that internal id."""
    for parts in lines(tree):
        if len(parts) > 1 and parts[1].endswith("@" + uid):
            return True
    return False


def any_decided(tree):
    """Say whether the log holds a decision on any proposal: an approval, a rejection or a stale close."""
    return any(len(parts) > 1 and ID.search(parts[1]) for parts in lines(tree))


def approved_subjects(tree):
    """(the internal ids, the paths) that a line of the log names as admitted: by an approval, by
    `adopt`, or as a hand edit the engine logged."""
    uids, paths = set(), set()
    for parts in lines(tree):
        if len(parts) >= 4 and (parts[1] == EDIT or parts[1] == ADOPT and parts[3].startswith(APPROVED)):
            paths.add(parts[2])
        elif len(parts) >= 5 and parts[4].startswith(APPROVED):
            uids.update(ID.findall(parts[3]))
    return uids, paths


def rejections(tree):
    """The rejecting lines of the log, as written."""
    return ["- " + SEP.join(parts) for parts in lines(tree) if len(parts) >= 5 and parts[4].startswith(REJECTED)]
