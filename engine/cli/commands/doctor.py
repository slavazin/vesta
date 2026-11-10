"""`doctor`: what the engine runs on and what it found in place."""
from __future__ import annotations

import sys

import datetime

import json

from cli import args
from kernel.shipped import MANIFEST
from kernel.errors import UsageError
from kernel.version import ENGINE
from model.abstractions import SourceError
from session import passes, state


def _is_file(tree, path):
    try:
        return tree.is_file(path)
    except ValueError:
        return False


def _age(opened, now):
    try:
        then = datetime.datetime.strptime(opened, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    except ValueError:
        return "unknown"
    minutes = int((now - then).total_seconds() // 60)
    if minutes < 60:
        return "%d minute%s" % (minutes, "" if minutes == 1 else "s")
    if minutes < 48 * 60:
        return "%d hour%s" % (minutes // 60, "" if minutes // 60 == 1 else "s")
    return "%d days" % (minutes // (24 * 60))


def run(context, arguments):
    args.split(arguments)
    config = context.config
    context.write("# Doctor")
    context.write()
    context.write("- Python: %d.%d.%d" % tuple(sys.version_info[:3]))
    context.write("- Engine: %s, reading schema %d" % (ENGINE, config.schema))
    context.write("- Project root: %s" % context.root)
    try:
        source, note = context.change_source()
        context.write("- Changed files are found by: %s%s" % (source.id, " (%s)" % note if note else ""))
        context.write("  It does not see: %s." % source.residue)
    except SourceError as error:
        context.write("- Changed files cannot be found: %s" % error)
    if not config.pointer_file:
        context.write("- Pointer file: none; the owner types `/vesta-hook`, `/vesta-insight` and `/vesta-learn` by hand")
    elif _is_file(context.tree, config.pointer_file):
        context.write("- Pointer file: %s" % config.pointer_file)
    else:
        context.write("- Pointer file: %s, which is not in the project" % config.pointer_file)
    context.write("- Approver name on record: %s" % (config.owner or "none; an approval is recorded without one"))
    context.write("- Engagement: %s" % config.engagement)
    unclosed = state.open_ones(context.tree)
    context.write("- Sessions not closed: %s" % (len(unclosed) or "none"))
    now = context.clock.now()
    for session in unclosed:
        context.write("  - %s; age: %s" % (session.one_line(), _age(session.opened, now)))
    for path in state.unreadable(context.tree):
        context.write("- A session file does not read: %s. It is the engine's working state and no record, so this one file may be deleted by hand." % path)
    try:
        found = passes.read(context.tree)
        context.write("- Learn pass: %s" % ("%s is open, opened %s; `walk learn` goes on with it" % (found.id, found.opened) if found else "none open"))
    except UsageError as error:
        context.write("- Learn pass: %s" % error)
    try:
        listed = json.loads(context.tree.read(MANIFEST)) if _is_file(context.tree, MANIFEST) else None
    except (OSError, ValueError, UnicodeDecodeError):
        listed = None
    if not isinstance(listed, dict):
        context.write(
            "- %s is missing or does not read. It records the shipped files as this project received them; without it "
            "an upgrade leaves every file that differs as it is and writes the new text beside it." % MANIFEST
        )
    damage = context.shipped.whole()
    if damage:
        context.write("- This copy of the engine is not whole (%d file%s; the first: %s). `/vesta-init upgrade` replaces it." % (len(damage), "" if len(damage) == 1 else "s", damage[0]))
    if unclosed:
        context.write("  Close one with `walk close --short --session <id>`, or leave it with `session abandon <id>`.")
    return 0
