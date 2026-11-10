"""The abstractions the engine is built from. Each concrete member implements one of these and is
named in one place, the manifest of the command line. Nothing here knows a concrete member.
"""
from __future__ import annotations

import abc

ROLES = ("when", "why", "except", "paths", "triggers")

# The lifecycle roles. A record type whose fields play them takes part in replacement, retirement and
# archiving. Each role is played by the field of the same name unless the schema block's `lifecycle`
# key names another, so shared code asks the type for the field and never names one.
STATUS = "status"
ACCEPTED = "accepted"
SUPERSEDED = "superseded"
RETIRED = "retired"
SUPERSEDES = "supersedes"
SUPERSEDED_BY = "superseded-by"
RETIRED_BECAUSE = "retired-because"
DISPOSITION = "disposition"
OPEN = "open"
DECIDED = "decided"
APPROVED_BY = "approved-by"
OUTCOME = "outcome"
LIFECYCLE = (STATUS, SUPERSEDES, SUPERSEDED_BY, RETIRED_BECAUSE, DISPOSITION, DECIDED, APPROVED_BY, OUTCOME)


class RecordType(abc.ABC):
    """What a store's records look like: built from the schema block of the store's SCHEMA.md."""

    layout = "flat"
    title_required = True
    fields = ()
    sections = ()
    roles = {}
    lifecycle = {}
    payload_section = ""
    conditions = ()

    @abc.abstractmethod
    def field(self, name):
        """The field of that name, or None."""
        raise NotImplementedError

    def role_field(self, role):
        """The name of the field that plays an index role, or None where no field does."""
        return self.roles.get(role)

    def role(self, record, role):
        """What a record holds in the field that plays an index role; None where no field does."""
        name = self.role_field(role)
        return None if name is None else record.get(name)

    def life_field(self, role):
        """The name of the field that plays a lifecycle role: the one the type names for it, else the
        field of the role's own name; None where the type has neither."""
        name = self.lifecycle.get(role, role)
        return name if self.field(name) is not None else None

    def life(self, record, role):
        """What a record holds in the field that plays a lifecycle role; None where no field does."""
        name = self.life_field(role)
        return None if name is None else record.get(name)

    def is_accepted(self, record):
        """Say whether a record is in force. A type with no status field has no other kind."""
        if self.life_field(STATUS) is None:
            return True
        return self.life(record, STATUS) == ACCEPTED

    @abc.abstractmethod
    def validate(self, record):
        """The problems of one record against this type, as a list of Problem."""
        raise NotImplementedError

    @abc.abstractmethod
    def front(self, record):
        """The record's frontmatter as a mapping in the written order, every field present."""
        raise NotImplementedError


class Store(abc.ABC):
    """One folder of records of one type under one write discipline, read and written through one tree.

    `settings` is the store's configuration entry (name, path, kind, recall, governed, label);
    `type` its record type; `path` its folder.
    """

    name = ""
    path = ""
    settings = None
    type = None

    @abc.abstractmethod
    def paths(self):
        """The path of every record file, sorted."""

    @abc.abstractmethod
    def scan(self):
        """[(path, record or None, problems)] for every record file; a file that does not read has no record."""

    @abc.abstractmethod
    def list(self):
        """Every record that reads, sorted by label."""

    @abc.abstractmethod
    def get(self, ref):
        """The record a label, an internal id or a joined reference names, or None."""

    @abc.abstractmethod
    def locate(self, ref):
        """The path of that record, or None."""

    @abc.abstractmethod
    def title(self, record):
        """The record's title line, or an empty text."""

    @abc.abstractmethod
    def write(self, record, relabel=False):
        """Write a record in the canonical form. In a ledger, refuses a change to a field not marked
        mutable; `relabel` lets the label change and nothing else."""

    @abc.abstractmethod
    def next_id(self, seed, also=()):
        """A fresh (internal id, label) for a record about to be written. `also` holds labels used
        outside the store's own folder."""


class Matcher(abc.ABC):
    """A mechanical match. Judgment is never a matcher.

    A matcher that a probe names by its keyword also reads its subject without evaluating it
    (`parse`), and says how many files it could not read (`skipped`).
    """

    id = ""
    skipped = 0

    def parse(self, subject):
        """Raise MatchError where the subject is not one this matcher can evaluate."""
        return subject

    @abc.abstractmethod
    def match(self, subject, context):
        """True or False; raises MatchError where the match cannot be evaluated."""
        raise NotImplementedError


class MatchError(Exception):
    """A match that could not be evaluated, with the reason."""


class Section(object):
    """What a step prints: a title, the lines of data it gathered, and the instruction."""

    def __init__(self, title, data, instruction):
        self.title = title
        self.data = data
        self.instruction = instruction


class Step(abc.ABC):
    """One unit of a walk: it gathers data and prints an instruction.

    `live`: its data exists only after earlier steps of the walk have been carried out, so a part
    of the sheet ends before it. `joins`: a live step that is printed in the same part as the live
    step before it, where there is one. `needs`: `bundle` or `conversation`. `always`: it prints `none`
    where its data is empty. `on_request`: it prints only where the walk names it. `lowest_level`:
    the lowest engagement level at which it prints. `reads`: the sections of the checkpoint's walk
    file it prints, which the `walks` check then expects to find.
    """

    id = ""
    title = ""
    live = False
    joins = False
    needs = "bundle"
    always = True
    on_request = False
    lowest_level = "quiet"
    reads = ()

    def present(self, context):
        """Say whether the step has a section in this walk at all. It reads only what stands still
        while the walk is carried out, so every part of a sheet numbers the steps alike."""
        return True

    @abc.abstractmethod
    def render(self, context):
        """The Section the step prints: its title, the lines of data it gathered, its instruction."""
        raise NotImplementedError


class Opening(abc.ABC):
    """What a walk does before its first step: which session or pass the walk belongs to.

    One member serves every checkpoint that names no other; a checkpoint whose walk opens
    differently has a member of its own. `flags` are the command-line flags the member reads,
    beyond the ask and the session every opening is given; each reaches `open` under its name
    without the dashes.
    """

    flags = ()

    @abc.abstractmethod
    def open(self, context, options):
        """(the session the walk runs in, opened or found; the lines that say what was done).
        `options` holds what the command line gave."""
        raise NotImplementedError

    def paths(self, context, session, given):
        """The paths the walk's mechanical matches run against: the ones the command line gave,
        unless the member has a better source for a walk that names none."""
        return list(given)


class KindError(Exception):
    """A change a proposal describes that cannot be made as written, with the reason."""


class Change(object):
    """What applying a proposal does to its target.

    `writes` is `{path: new text}` and `moves` `[(from, to)]`. `replaced` lists `(what, the value or
    text that was there)`, for the proposal's own record of what it changed. `subject` names what
    the change landed as or in: a record reference, or a file. `created` says whether the subject
    is a record the change brought into being. `renamed` maps each label the change renames to its
    new one.
    """

    def __init__(self, subject, created=False):
        self.subject = subject
        self.created = created
        self.writes = {}
        self.moves = []
        self.replaced = []
        self.renamed = {}


class ProposalKind(abc.ABC):
    """One kind of lasting change.

    `draft`: the kind creates a record, whose full text is drafted in a file beside the proposal.
    """

    id = ""
    draft = False

    @abc.abstractmethod
    def resolve(self, target, context):
        """What the target names, in the form the kind works on. Raises KindError where it names
        nothing this kind can change."""
        raise NotImplementedError

    @abc.abstractmethod
    def scaffold(self, target, context, label):
        """The text the Change section of a new proposal of that label starts with, for the drafter to fill."""
        raise NotImplementedError

    def home(self, target, context):
        """(the store a draft becomes a record of, the records it replaces), for a kind that has a draft."""
        return None, []

    def draft_text(self, target, context):
        """The text a new draft starts with, for a kind that has one."""
        return ""

    @abc.abstractmethod
    def validate(self, proposal, context):
        """What is wrong with the proposal as drafted, as a list of sentences; empty where it could
        be applied."""
        raise NotImplementedError

    @abc.abstractmethod
    def changes(self, proposal, context, approver):
        """The Change the proposal describes. Raises KindError where it cannot be made."""
        raise NotImplementedError

    @abc.abstractmethod
    def standing_cost(self, target, context):
        """What the change would cost every later session, in words."""
        raise NotImplementedError


class Check(abc.ABC):
    """A mechanical validation. `residue` states what it does not verify."""

    id = ""
    residue = ""

    @abc.abstractmethod
    def run(self, context):
        """A list of Finding."""
        raise NotImplementedError


class SourceError(Exception):
    """A change source that could not read the project, with the reason."""


class ChangeSource(abc.ABC):
    """How the engine learns which paths a session changed.

    Built from the project root, the tree, and the directory names to skip. A base is a mapping
    that names its source under `source`, so a later command reads it with the source that made it.
    """

    id = ""
    residue = ""

    def __init__(self, root, tree, ignore=()):
        self.root = root
        self.tree = tree
        self.ignore = tuple(ignore)

    @classmethod
    def usable(cls, root):
        """(True, "") where this source can read the project at that root, else (False, why not)."""
        return True, ""

    @abc.abstractmethod
    def mark(self):
        """A base to compare against later."""
        raise NotImplementedError

    @abc.abstractmethod
    def changed_since(self, base):
        """The sorted paths changed since the base. Raises SourceError where it cannot tell."""
        raise NotImplementedError


class CaptureSource(abc.ABC):
    """Where the owner's corrections are gathered from."""

    id = ""

    @abc.abstractmethod
    def steers(self, session):
        raise NotImplementedError
