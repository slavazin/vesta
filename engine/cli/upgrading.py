"""An upgrade that is part-way through: the record it leaves, and what a later command does with it.

An upgrade brings the files under vesta/ up to date in one commit and then puts the new engine in
the place of the old one. Between the two it leaves a record holding its report, so that a stop
there loses nothing: the upgrade run again, or the next command of the new engine, finishes from it.
The record names the list of shipped files that commit wrote, so a record whose files were since
put back, or brought further, is known to be stale and is not trusted.
"""
from __future__ import annotations

import json
import os

from kernel import root as roots
from kernel import version
from kernel.shipped import MANIFEST, digest

PATH = "vesta/.state/upgrade.json"


def record(start, report, listing):
    """The record: the version the upgrade started from, the one it goes to, its report, and the
    fingerprint of the list of shipped files its commit writes."""
    return {"from": start or "", "to": version.ENGINE, "report": list(report), "files": digest(listing)}


def text(found):
    return json.dumps(found, indent=1, sort_keys=True) + "\n"


def _parsed(text):
    try:
        return version.parse(text)
    except ValueError:
        return None


def read(tree):
    """The record of an upgrade whose files are in place and whose engine may not be, or None:
    where there is none, where it does not read, or where the files are no longer as it left them."""
    try:
        if not tree.is_file(PATH):
            return None
        found = json.loads(tree.read(PATH))
        if not isinstance(found, dict) or not isinstance(found.get("to"), str) or not isinstance(found.get("report"), list):
            return None
        if _parsed(found["to"]) is None or not tree.is_file(MANIFEST) or digest(tree.read(MANIFEST)) != found.get("files"):
            return None
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    return {"from": str(found.get("from") or ""), "to": found["to"], "report": [str(line) for line in found["report"]], "files": found["files"]}


def drop(tree):
    """Remove the record. Says whether this call was the one that removed it."""
    try:
        os.remove(tree.locate(PATH))
        return True
    except OSError:
        return False


def report(found):
    """The lines an upgrade prints once its engine is in place."""
    lines = ["Upgraded the engine from %s to %s. It is now in vesta/%s." % (found["from"] or "an unknown version", found["to"], roots.ENGINES[0])]
    return lines + found["report"]


def notes(tree, engine_dir):
    """What a command other than `upgrade` says where an upgrade's record is still there, as lines.
    Where this engine is the one the upgrade was putting in place, the upgrade is over: its report
    is printed, once, and the record removed. A record that is stale is removed and not spoken of."""
    if not tree.is_file(PATH):
        return []
    found = read(tree)
    here = os.path.basename(os.path.abspath(engine_dir)) == roots.ENGINES[0]
    if found is None or (here and _parsed(found["to"]) < version.parse(version.ENGINE)):
        drop(tree)
        return []
    if here and found["to"] == version.ENGINE:
        if not drop(tree):
            return []
        return ["Note: an upgrade finished just before this command. Its report, for the owner:"] + ["  " + line for line in report(found)] + [""]
    return [
        "Note: an upgrade to engine %s brought the files under vesta/ up to date and stopped before the engine itself was put in "
        "place. `/vesta-init upgrade` finishes it. Tell the owner an upgrade is unfinished." % found["to"]
    ]
