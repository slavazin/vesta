"""Builds the context a command runs in: the tree, the configuration, the stores."""
from __future__ import annotations

import os

from cli import manifest
from kernel.shipped import Shipped
from kernel.clock import Clock
from kernel.errors import UsageError
from model.abstractions import SourceError
from kernel.tree import DiskTree
from model import config as configuration
from model.context import Context, Stores
from stores import schema
from stores.filestore import FileStore


def stores_over(tree, config, clock):
    """The project's stores as a tree shows them. A store whose SCHEMA.md does not read is left out
    and its problems kept for the `layout` check."""
    stores = Stores()
    for name, settings in config.stores.items():
        path = settings.path + "/" + schema.FILE
        if not tree.is_file(path):
            stores.unreadable[name] = []
            continue
        try:
            record_type, problems = schema.read(tree.read(path), path)
        except UnicodeDecodeError:
            record_type, problems = None, [(1, "the file is not UTF-8 text")]
        if record_type is None:
            stores.unreadable[name] = problems
        else:
            stores.add(FileStore(settings, record_type, tree, clock))
    return stores


def context(root, out, clock=None, tree=None):
    """The context for a project root. Raises UsageError where the folder has no readable configuration."""
    tree = tree if tree is not None else DiskTree(root)
    clock = clock if clock is not None else Clock()
    if not tree.is_file(configuration.PATH):
        raise UsageError("there is no %s under %s; run `/vesta-init` in the project first" % (configuration.PATH, root))
    try:
        text = tree.read(configuration.PATH)
    except UnicodeDecodeError:
        raise UsageError("%s is not UTF-8 text; save it as UTF-8 and run the command again" % configuration.PATH)
    config = configuration.load(text)
    for name, entry in manifest.CHECKPOINTS.items():
        # A project that names no such walk has the shipped one while its file is there; deleting the file removes it.
        if tree.is_file(configuration.HOME + "/" + entry["walk"]):
            config.checkpoints.setdefault(name, configuration.Checkpoint(name, entry))
    return Context(root, tree, config, stores_over(tree, config, clock), clock, manifest.known(), out, text, shipped(), Services())


class Services(object):
    """What the layers below the command line ask of it: a member by id, and the change source."""

    def member(self, table, name):
        return manifest.member(table, name)

    def change_source(self, context, name=None):
        return change_source(context, name)


def change_source(context, name=None):
    """(the change source, a note on the choice).

    With a name, the source of that id. With none, the one `adapters.changes` names; `auto` takes
    the first source of the manifest's order that can read the project, and the note says why each
    earlier one was passed over. Raises SourceError where no source can be used.
    """
    config = context.config
    wanted = name or config.changes
    if wanted == configuration.AUTO:
        passed = []
        for candidate in manifest.AUTO:
            member = manifest.member("changes", candidate)
            usable, why = member.usable(context.root)
            if usable:
                note = "; ".join("`%s` is not used: %s" % pair for pair in passed)
                return member(context.root, context.tree, config.ignore), note
            passed.append((candidate, why))
        raise SourceError("no way of finding changed files can be used here: %s" % "; ".join("`%s`: %s" % pair for pair in passed))
    if wanted not in manifest.CHANGES:
        raise SourceError("`%s` is not a way of finding changed files this engine has; it has: %s" % (wanted, ", ".join(sorted(manifest.CHANGES))))
    member = manifest.member("changes", wanted)
    usable, why = member.usable(context.root)
    if not usable:
        raise SourceError("`%s` cannot be used to find changed files: %s" % (wanted, why))
    return member(context.root, context.tree, config.ignore), ""


def shipped():
    """The shipped text of this engine."""
    return Shipped(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
