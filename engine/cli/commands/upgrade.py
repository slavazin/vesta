"""`upgrade`: run from `vesta/.engine.next/`, a newer copy of the engine. It migrates the folder,
replaces each shipped file the project has not changed, leaves `<name>.new` beside each it has, and
then takes the place of `vesta/.engine/`.

The files change in one commit, which also holds the report; the engine is put in place after it.
A stop at any point is finished by running the command again (cli/upgrading.py).
"""
from __future__ import annotations

import json
import os
import re

from checks import pointer_block
from cli import args, build, handedits, manifest, upgrading
from cli.commands import check
from kernel import glob
from kernel import root as roots
from kernel import tree as trees
from kernel import version, yamlsubset
from kernel.errors import Refusal, SubsetError, UsageError
from kernel.finding import ERROR
from kernel.shipped import MANIFEST, digest, listing
from model import config as configuration
from proposals import admitted
from stores import admissions

BEFORE_SETUP = True
ALONE = True
NEW = ".new"
ENGINE_LINE = re.compile(r'^ENGINE = "([0-9]+\.[0-9]+\.[0-9]+)"', re.M)
SCHEMA_LINE = re.compile(r"(?m)^(schema:[ \t]*)[0-9]+")
NEXT = roots.FOLDER + "/" + roots.ENGINES[1]
# The rule as this version ships it: the folder's own copy may be an earlier version's, or changed.
RULE = NEXT + "/templates/vesta/INTERNALS.md, Upgrades"
UNCHANGED = "Nothing was changed."
# Shipped files an upgrade neither replaces nor writes a new copy beside. The configuration holds
# the project's own answers, and a key it leaves out runs at its default; the logs hold the
# project's history.
KEPT = ("vesta.yml", "log/**")
SHOWN = 5


def _kept(relative):
    return any(glob.match(pattern, relative) for pattern in KEPT)


def _here():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _placed():
    """Refuse an engine that is not a real folder at vesta/.engine.next."""
    here = _here()
    if os.path.basename(here) != roots.ENGINES[1]:
        raise UsageError(
            "`upgrade` is run by the new engine, not the one in place: copy the `engine/` folder of the vesta-init skill to "
            "%s and run `python3 \"<project>/%s\" upgrade`" % (NEXT, NEXT)
        )
    if os.path.islink(here):
        raise Refusal(
            "%s is a link to a folder elsewhere, and the engine in a project is a copy inside it. Remove the link and copy the "
            "`engine/` folder of the vesta-init skill there. %s" % (NEXT, UNCHANGED), RULE,
        )


def _installed(root):
    """The version of the engine in place, or None where there is none that reads."""
    path = os.path.join(root, roots.FOLDER, roots.ENGINES[0], "kernel", "version.py")
    try:
        with open(path, encoding="utf-8") as handle:
            found = ENGINE_LINE.search(handle.read())
    except (OSError, UnicodeDecodeError):
        return None
    return found.group(1) if found else None


def _schema(tree):
    """The schema the folder says it is at. Raises UsageError where it does not say."""
    try:
        data = yamlsubset.read(tree.read(configuration.PATH), configuration.PATH)
    except SubsetError as error:
        raise UsageError("the configuration does not read: %s. %s" % (error, UNCHANGED))
    number = data.get("schema") if isinstance(data, dict) else None
    if not isinstance(number, int) or isinstance(number, bool) or number < 1 or not SCHEMA_LINE.search(tree.read(configuration.PATH)):
        raise UsageError(
            "%s does not say which schema the folder is at, on a line of its own such as `schema: 1`, so the upgrade cannot "
            "tell what the folder needs. Put that line back as it was. %s" % (configuration.PATH, UNCHANGED)
        )
    return number


def _whole(shipped):
    damage = shipped.whole()
    if damage:
        more = len(damage) - SHOWN
        raise UsageError(
            "this copy of the engine is not whole: %s%s. Remove %s and copy it again. %s"
            % ("; ".join(damage[:SHOWN]), "; and %d more" % more if more > 0 else "", NEXT, UNCHANGED)
        )


def _strict_files(tree):
    """The configuration and every store's schema file, as they stand on disk."""
    found = [configuration.PATH] if tree.is_file(configuration.PATH) else []
    for name in tree.list(roots.FOLDER):
        path = "%s/%s/%s" % (roots.FOLDER, name, admitted.SCHEMA)
        if not name.startswith(".") and tree.is_dir(roots.FOLDER + "/" + name) and tree.is_file(path):
            found.append(path)
    return found


def _unaccepted(tree):
    """Refuse while a file the folder is governed by was changed by hand and the engine in place
    has not settled it: an upgrade is a change like any other, and writes over no hand edit."""
    try:
        recorded = json.loads(tree.read(admitted.PATH)) if tree.is_file(admitted.PATH) else None
    except (ValueError, UnicodeDecodeError):
        recorded = None
    if not isinstance(recorded, dict):
        raise Refusal(
            "%s is missing or does not read, so the upgrade cannot tell what was changed by hand. Put the file back from version "
            "control or a copy; `check` with the engine in place shows whether it reads. %s" % (admitted.PATH, UNCHANGED),
            RULE,
        )
    edited = sorted(path for path, mark in recorded.items() if not tree.is_file(path) or digest(tree.read(path)) != mark)
    waiting = sorted(set(path for path in edited if handedits.strict(path)) | set(path for path in _strict_files(tree) if path not in recorded))
    if waiting:
        raise Refusal(
            "an upgrade cannot be done while %s changed by hand and not accepted. With the engine in place, accept %s with "
            "`adopt <path>` once the owner has seen it, or put it back as it was; then run this command again. %s"
            % (", ".join(waiting) + (" is" if len(waiting) == 1 else " are"), "it" if len(waiting) == 1 else "each", UNCHANGED),
            RULE,
        )
    if edited:
        raise Refusal(
            "%s changed by hand since the engine in place last ran, and that is not logged yet. Run `check` with the engine in "
            "place, which logs it, then run this command again. %s"
            % (", ".join(edited) + (" was" if len(edited) == 1 else " were"), UNCHANGED),
            RULE,
        )


def _before(tree):
    """(the fingerprints of the shipped files as the last install or upgrade left them, whether that record read)."""
    try:
        found = json.loads(tree.read(MANIFEST)) if tree.is_file(MANIFEST) else None
    except (ValueError, UnicodeDecodeError):
        found = None
    if not isinstance(found, dict):
        return {}, False
    return dict((str(key), str(value)) for key, value in found.items()), True


class Plan(object):
    """What an upgrade does with each shipped file: the policy, apart from the writing."""

    def __init__(self, shipped, tree, before, disk=None):
        """`tree` is the folder as the migrations left it; `disk`, the folder as the project left
        it, is what says whether the project changed a file."""
        disk = disk if disk is not None else tree
        self.after = {}
        self.replaced, self.added, self.left, self.gone, self.blocked, self.stale = [], [], [], [], [], []
        self.writes = {}
        for relative in shipped.project_files():
            path, text = roots.FOLDER + "/" + relative, shipped.project_text(relative)
            mark = self.after[relative] = digest(text)
            if _kept(relative):
                continue
            if not tree.is_file(path):
                if relative in before:
                    self.gone.append(path)
                else:
                    self.writes[path] = text
                    self.added.append(path)
                continue
            beside = digest(tree.read(path + NEW)) if tree.is_file(path + NEW) else None
            now = digest(tree.read(path))
            mine = digest(disk.read(path)) if disk.is_file(path) else now
            # A file the project left alone is replaced, unless a migration has just rewritten it:
            # then it is as the new schema needs it.
            if now == mark or mine == before.get(relative):
                if now != mark and now == mine:
                    self.writes[path] = text
                    self.replaced.append(path)
                if beside is not None:
                    self.stale.append(path + NEW)  # a new text from an earlier upgrade, beside a file now current
                continue
            # The project changed the file. The shipped text is kept beside it, where it is not
            # there already and is not the text the project started from.
            if beside == mark or (beside is not None and before.get(relative) == mark):
                self.left.append(path)
            elif before.get(relative) != mark:
                if beside is not None:
                    self.blocked.append(path + NEW)
                else:
                    self.writes[path + NEW] = text
                    self.left.append(path)


def _migrate(overlay, schema):
    """Run the migrations from the folder's schema to this engine's, and write the new number."""
    try:
        steps = manifest.migrations(schema, version.SCHEMA)
    except LookupError as error:
        raise UsageError("%s. Remove %s. %s" % (error, NEXT, UNCHANGED))
    for number, migrate in enumerate(steps, schema):
        try:
            migrate(overlay)
        except (Refusal, UsageError):
            raise
        except Exception as error:
            raise UsageError(
                "the migration from schema %d to schema %d stopped (%s: %s). Remove %s. %s"
                % (number, number + 1, type(error).__name__, error, NEXT, UNCHANGED)
            )
    moved = [path for path in overlay.changed() if path != configuration.PATH]
    if steps:
        text, count = SCHEMA_LINE.subn(lambda found: found.group(1) + str(version.SCHEMA), overlay.read(configuration.PATH), count=1)
        if count != 1:
            raise UsageError("a migration left %s without its `schema:` line. %s" % (configuration.PATH, UNCHANGED))
        overlay.write(configuration.PATH, text)
    return len(steps), moved, configuration.PATH in overlay.changed()


def _fingerprints(tree, overlay, context):
    """Bring the recorded fingerprints up to date for what this upgrade wrote or removed. A file
    that was changed by hand before it keeps its old fingerprint, so the hand edit is still seen."""
    recorded = admitted.read(tree)
    governed = set(admitted.governed_paths(overlay, context.config, context.stores))
    for path in overlay.changed():
        untouched = not tree.is_file(path) or recorded.get(path) == digest(tree.read(path))
        if not untouched:
            continue
        if path in governed:
            recorded[path] = digest(overlay.read(path))
        elif path in recorded and not overlay.is_file(path):
            del recorded[path]
    overlay.write(admitted.PATH, admitted.text(recorded))


def _keys(data, prefix=""):
    found = set()
    for key, value in data.items() if isinstance(data, dict) else ():
        found.add(prefix + str(key))
        found |= _keys(value, prefix + str(key) + ".")
    return found


def _new_settings(shipped, overlay):
    """The settings the shipped configuration names and this project's does not."""
    try:
        theirs = yamlsubset.read(shipped.project_text(roots.CONFIG), roots.CONFIG)
        mine = yamlsubset.read(overlay.read(configuration.PATH), configuration.PATH)
    except (OSError, SubsetError):
        return []
    fresh = _keys(theirs) - _keys(mine)
    return sorted(key for key in fresh if not any(key.startswith(other + ".") for other in fresh))


def _errors(context):
    return [finding for finding in check.findings(context)[0] if finding.severity == ERROR]


def _sound(root, out, clock, after):
    """Refuse an upgrade that would leave the folder with an error it does not have now."""
    try:
        known = set((finding.check, finding.file, finding.message) for finding in _errors(build.context(root, out, clock)))
    except (UsageError, SubsetError):
        known = None  # this engine cannot read the folder as it stands; every error after counts
    fresh = [finding for finding in _errors(after) if (finding.check, finding.file, finding.message) not in (known or ())]
    if fresh:
        listed = "\n".join("- " + finding.render() for finding in fresh)
        if known is None:
            raise Refusal(
                "after this upgrade `check` would report %d error%s:\n%s\nAn error that is there already is settled first, with the "
                "engine in place: `check` shows them. Then run this command again. %s"
                % (len(fresh), "" if len(fresh) == 1 else "s", listed, UNCHANGED),
                RULE,
            )
        raise Refusal(
            "this upgrade would leave the project with %d error%s it does not have now:\n%s\nRemove %s. %s"
            % (len(fresh), "" if len(fresh) == 1 else "s", listed, NEXT, UNCHANGED),
            RULE,
        )


def _block(context):
    """A line where the project's agent-instruction file holds the earlier version's block."""
    path = context.config.pointer_file
    try:
        if not path or not context.tree.is_file(path):
            return []
        block = pointer_block.block_of(context.tree.read(path))[0]
        if block is None or block == context.shipped.read(pointer_block.SHIPPED):
            return []
    except (OSError, ValueError, UnicodeDecodeError):
        return []
    return [
        "The Vesta block in %s is the earlier version's, and `check` reports it until it is replaced. With the owner's "
        "consent, replace it, its two marker lines included, with the text of %s." % (path, pointer_block.WHERE)
    ]


def _report(plan, steps, moved, schema, read, settings, block, config_changed):
    lines = []
    if steps:
        lines.append("The folder was brought from schema %d to schema %d.%s" % (
            schema, version.SCHEMA, " That changed or moved: %s." % ", ".join(moved) if moved else "",
        ))
    if not read:
        lines.append(
            "%s was missing or did not read, so the upgrade could not tell which files this project had changed: "
            "every one that differs from the new text was left as it is." % MANIFEST
        )
    for title, paths in (
        ("Replaced with the new shipped text, since this project had not changed them", plan.replaced),
        ("New in this version", plan.added),
    ):
        lines.append("%s: %s" % (title, ", ".join(paths) or "none"))
    if plan.left:
        lines.append(
            "%s, so left as they are; the new shipped text is beside each as `<name>%s`, for the owner to merge and then delete:"
            % ("Changed in this project" if read else "Different from the new shipped text", NEW)
        )
        lines.extend("- %s (new text: %s%s)" % (path, path, NEW) for path in plan.left)
    else:
        lines.append("Left for the owner to merge: none")
    if plan.stale:
        lines.append("Left by an earlier upgrade beside a file that is now current, for the owner to delete: %s" % ", ".join(plan.stale))
    if plan.gone:
        lines.append("Removed in this project, and not put back: %s" % ", ".join(plan.gone))
    lines.append(
        "%s holds this project's own settings; %s." % (configuration.PATH, "the upgrade changed what the new schema needs in it and nothing else" if config_changed else "it was left as it is")
    )
    if settings:
        lines.append(
            "Settings this version knows and this project's %s does not name; each runs as this version ships it until the project sets it "
            "through a `config` proposal: %s." % (configuration.PATH, ", ".join(settings))
        )
    lines.extend(block)
    lines.append("Run `check` with the engine in place to see that the folder reads.")
    return lines


def _place(root, tree, out, found):
    """Put this engine in place, print the report the commit kept, and drop the record."""
    try:
        roots.swap(root)
    except OSError as error:
        raise UsageError(
            "the files under vesta/ are at the new version, and the new engine could not be put in place of the old one (%s). "
            "Close whatever holds a file under vesta/%s or %s open and run this command again: it goes on from here, and the report is kept."
            % (error, roots.ENGINES[0], NEXT)
        )
    upgrading.drop(tree)
    for line in upgrading.report(found):
        out.write(line + "\n")
    return 0


def run_bare(root, arguments, out, clock):
    args.split(arguments)
    _placed()
    tree = trees.DiskTree(root)
    if not tree.is_file(configuration.PATH):
        raise UsageError("Vesta is not set up in this project (%s is missing); `init` sets it up" % configuration.PATH)
    shipped = build.shipped()
    _whole(shipped)
    installed = _installed(root)
    if installed and version.parse(installed) > version.parse(version.ENGINE):
        raise Refusal(
            "the engine in place is %s and this one is %s: an upgrade never goes back. Remove %s. %s"
            % (installed, version.ENGINE, NEXT, UNCHANGED), RULE,
        )
    earlier = upgrading.read(tree)
    if earlier is None:
        upgrading.drop(tree)  # a record whose files were put back, or that does not read, says nothing
    elif earlier["to"] == version.ENGINE:
        return _place(root, tree, out, earlier)
    elif version.parse(earlier["to"]) > version.parse(version.ENGINE):
        raise Refusal(
            "an upgrade to engine %s already brought the files under vesta/ up to date, and this engine is %s: an upgrade never "
            "goes back. Copy the %s engine to %s and run this command again. %s"
            % (earlier["to"], version.ENGINE, earlier["to"], NEXT, UNCHANGED), RULE,
        )
    schema = _schema(tree)
    if schema > version.SCHEMA:
        raise Refusal(
            "this folder is at schema %d and this engine reads up to %d: it is older than the folder. Remove %s. %s"
            % (schema, version.SCHEMA, NEXT, UNCHANGED), RULE,
        )
    _unaccepted(tree)
    overlay = trees.Overlay(tree)
    steps, moved, config_changed = _migrate(overlay, schema)
    before, read = _before(tree)
    plan = Plan(shipped, overlay, before, tree)
    if plan.blocked:
        raise Refusal(
            "an earlier upgrade left %s, and this one has a newer text to put there. Merge what the owner wants from %s "
            "and delete %s, then run this command again. %s"
            % (", ".join(plan.blocked), "it" if len(plan.blocked) == 1 else "each", "it" if len(plan.blocked) == 1 else "them", UNCHANGED),
            RULE,
        )
    for path, text in sorted(plan.writes.items()):
        overlay.write(path, text)
    overlay.write(MANIFEST, listing(plan.after))
    context = build.context(root, out, clock, overlay)
    _fingerprints(tree, overlay, context)
    context = build.context(root, out, clock, overlay)
    _sound(root, out, clock, context)
    count = len(plan.replaced) + len(plan.added)
    if steps or count or plan.left or installed != version.ENGINE:
        line = "- %s · upgrade · engine %s to %s · schema %d to %d · %d file%s replaced\n" % (
            context.clock.today(), installed or "unknown", version.ENGINE, schema, version.SCHEMA, count, "" if count == 1 else "s",
        )
        overlay.write(admissions.PATH, admissions.with_line(overlay, line))
    report = _report(plan, steps, moved, schema, read, _new_settings(shipped, overlay), _block(context), config_changed)
    if earlier is not None:
        report = ["An upgrade to engine %s was started before this one and not finished. What it reported:" % earlier["to"]] + [
            "  " + line for line in earlier["report"]
        ] + ["This upgrade:"] + report
    found = upgrading.record(installed, report, listing(plan.after))
    overlay.write(upgrading.PATH, upgrading.text(found))
    overlay.commit()
    return _place(root, tree, out, found)
