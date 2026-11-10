"""The manifest: the one place that names concrete members.

One table per abstraction, `{id: "module.path"}`. A module is imported only when the configuration, or
the command line, names its id; a member the configuration does not name is never imported. Each member
module exposes its class as `MEMBER`. A table grows with the slice that builds its members.
"""
from __future__ import annotations

import importlib

COMMANDS = {
    "version": "cli.commands.version",
    "check": "cli.commands.check",
    "show": "cli.commands.show",
    "index": "cli.commands.index",
    "scopes": "cli.commands.scopes",
    "init": "cli.commands.init",
    "doctor": "cli.commands.doctor",
    "walk": "cli.commands.walk",
    "load": "cli.commands.load",
    "mark": "cli.commands.mark",
    "jot": "cli.commands.jot",
    "triggers": "cli.commands.triggers",
    "session": "cli.commands.session",
    "obs": "cli.commands.obs",
    "propose": "cli.commands.propose",
    "proposals": "cli.commands.proposals",
    "apply": "cli.commands.apply",
    "reject": "cli.commands.reject",
    "adopt": "cli.commands.adopt",
    "relabel": "cli.commands.relabel",
    "pass": "cli.commands.passes",
    "upgrade": "cli.commands.upgrade",
}

SUMMARIES = {
    "version": "the engine version and the folder's schema number",
    "check": "run the checks the configuration names; exit 1 on an error",
    "show": "<id>…  print records in full",
    "index": "[--store <name>] [--all]  when to open each record",
    "scopes": "<path>…  the records whose paths cover each path",
    "init": "[--owner <name or ->] [--engagement <level>] [--pointer-file <path>]  set the folder up",
    "doctor": "what the engine runs on and what it found in place",
    "walk": "<checkpoint> [--ask <text or ->] [--paths <path>…] [--continue|--new|--parallel] [--short] [--with <step>] [--from <step>] [--session <id>]  print a part of a walk sheet",
    "load": "<id>… [--by index|trigger] [--session <id>]  print records in full and add them to the session",
    "mark": "<id>=<mark>… [--session <id>]  say what came of a loaded record: applied, not-applicable, should-have-loaded",
    "jot": "[--steer] [--anchor <a>] [--session <id>] <text or ->  note something in the session",
    "triggers": "every live trigger with the state of its probe",
    "session": "show | close | abandon <id>  [--session <id>]  read or end a session",
    "propose": "<kind> --target <t> [--evidence <id>,…] [--source <s>] [--draft <file>]  start a proposal for a lasting change",
    "proposals": "[<id>]  the proposals waiting for the owner; with an id, one in full with what is wrong with it, or a decided one as it was decided",
    "apply": "<id> [--ref <commit or note>] [--approved-by <name>]  make the change of a proposal the owner approved",
    "reject": "<id> --reason <text or -> [--ref <commit or note>] [--by <name>]  record that the owner turned a proposal down",
    "adopt": "<path> [--reason <text or ->] [--ref <commit or note>]  accept a schema or the configuration as it stands after a hand edit",
    "relabel": "<store> [--one <id>]  rename a store's records to its configured label form",
    "obs": "add | list [--open|--pass <n>] | dispose <id> --as <text or ->  [--store <name>] [--session <id>]  write observations from a JSON array on standard input, print them, or set one aside during a learn pass",
    "upgrade": "run from vesta/.engine.next: replace the engine in place with this newer copy, and bring the shipped files up to date",
    "pass": "seal [--hold <id>,…] [--note <file or ->]  end the open learn pass: archive what it read and write its note",
}

MATCHERS = {
    "scope": "matchers.scope",
}

# The probe forms, by the keyword a probe opens with.
PROBES = {
    "exists": "matchers.exists",
    "missing": "matchers.missing",
    "grep": "matchers.grep",
}

CHECKS = {
    "config": "checks.config",
    "layout": "checks.layout",
    "records": "checks.records",
    "lengths": "checks.lengths",
    "walks": "checks.walks",
    "links": "checks.links",
    "pointer-block": "checks.pointer_block",
    "language": "checks.language",
    "probes": "checks.probes",
    "admitted": "checks.admitted",
}

STEPS = {
    "recall": "steps.recall",
    "triggers": "steps.triggers",
    "rows": "steps.rows",
    "lenses": "steps.lenses",
    "notices": "steps.notices",
    "bundle": "steps.bundle",
    "marks": "steps.marks",
    "sweep": "steps.sweep",
    "contradictions": "steps.contradictions",
    "steers": "steps.steers",
    "mint": "steps.mint",
    "offers": "steps.offers",
    "surface": "steps.surface",
    "choices": "steps.choices",
    "window": "steps.window",
    "counts": "steps.counts",
    "trigger-review": "steps.trigger_review",
    "consolidate": "steps.consolidate",
    "group": "steps.group",
    "route": "steps.route",
    "draft": "steps.draft",
    "gate": "steps.gate",
    "seal": "steps.seal",
}
KINDS = {
    "add": "proposals.add",
    "supersede": "proposals.supersede",
    "merge": "proposals.merge",
    "retire": "proposals.retire",
    "latch-edit": "proposals.latch_edit",
    "correct": "proposals.correct",
    "resolve-trigger": "proposals.resolve_trigger",
    "row": "proposals.row",
    "lens": "proposals.lens",
    "language": "proposals.language",
    "schema": "proposals.schema",
    "config": "proposals.config",
}

# The change sources. `adapters.changes: auto` takes the first of AUTO that can read the project.
CHANGES = {
    "git": "adapters.git",
    "mtime": "adapters.mtime",
}
AUTO = ("git", "mtime")
CAPTURE = {
    "jot": "adapters.jot",
}

# How a walk opens, by checkpoint id. A checkpoint with no line of its own opens as DEFAULT_OPENING does.
OPENINGS = {
    "start": "session.start",
    "learn": "session.learn",
    "default": "session.late",
}
DEFAULT_OPENING = "default"

TABLES = {
    "steps": STEPS, "kinds": KINDS, "checks": CHECKS, "changes": CHANGES, "capture": CAPTURE,
    "matchers": MATCHERS, "probes": PROBES, "openings": OPENINGS,
}


def known():
    """The ids each table holds, for the `config` check."""
    return dict((name, sorted(table)) for name, table in TABLES.items())


def member(table, name):
    """The class of one member, importing its module now."""
    return importlib.import_module(TABLES[table][name]).MEMBER


# A migration is found by the schema step it makes: `migrations/m<from>_<to>.py`.
MIGRATION = "migrations.m%d_%d"


def migrations(start, end):
    """The migrate functions that take a folder from one schema to another, in order.
    Raises LookupError where a step has no module. The command that runs them writes the new
    schema number and brings the recorded fingerprints up to date; a migration does neither."""
    found = []
    for number in range(start, end):
        name = MIGRATION % (number, number + 1)
        try:
            found.append(importlib.import_module(name).migrate)
        except ImportError as error:
            if getattr(error, "name", None) != name:
                raise  # the migration is there and something it imports is not
            raise LookupError("this engine has no migration from schema %d to schema %d" % (number, number + 1))
    return found


def command(name):
    """The module of one command, or None."""
    return importlib.import_module(COMMANDS[name]) if name in COMMANDS else None
