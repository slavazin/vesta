"""The abstractions the engine is built from. Each concrete member implements one of these and is
named in one place, the manifest of the command line. Nothing here knows a concrete member.
"""
from __future__ import annotations

import abc
import hashlib

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
    beyond the ask and the session every opening is given, and `options` the ones that take a value;
    each reaches `open` under its name without the dashes.
    """

    flags = ()
    # The command-line options that take a value, read the same way.
    options = ()

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

    def lines(self, session, context):
        """What the source prints on a sheet: one line for each correction; empty where it holds none."""
        return [
            "- %s %s%s (from %s)" % (steer.get("at", ""), steer.get("text", ""), " (anchor: %s)" % steer["anchor"] if steer.get("anchor") else "", self.id)
            for steer in self.steers(session)
        ]


class HistoryError(Exception):
    """A place earlier conversations are kept that could not be read, with the reason."""


class Conversation(object):
    """One earlier conversation as a history lists it: the name the history gives it, when it was
    last added to (`YYYY-MM-DD`, or an empty text where that is not known), and the file it is in."""

    def __init__(self, ref, dated, path):
        self.ref = ref
        self.dated = dated
        self.path = path


class Turn(object):
    """One thing said in an earlier conversation. `who` is `owner`, `agent`, or an empty text where
    the history cannot tell."""

    OWNER, AGENT, UNKNOWN = "owner", "agent", ""

    def __init__(self, who, text, at="", mark=""):
        self.who = who
        # What cannot be written as UTF-8 is replaced here, so that nothing later meets it.
        self.text = text.encode("utf-8", "replace").decode("utf-8")
        self.at = at
        # What this one thing said is known by across readings: the history's own id for it, or a digest of its words.
        self.mark = mark or hashlib.sha256(self.text.encode("utf-8")).hexdigest()[:16]


class History(abc.ABC):
    """Where conversations with an agent that took place before now are kept, outside the project.

    Built from the project root and the path the command line gave, if any. A member reads and never
    writes. `name` is what the owner is told the place is; `residue` states what the member cannot
    find. `takes_path`: the owner may name the place; `needs_path`: the member reads no other.
    After `conversations`, `left_out` says what in the place was passed over, in words, or is empty.
    After `turns`, `unread` is how many lines could not be read, and `harness` how many things the
    harness itself wrote in the owner's place and were left out.
    """

    id = ""
    name = ""
    residue = ""
    takes_path = False
    needs_path = False
    left_out = ""
    # What the day of a conversation is, where the history knows only its file.
    day_word = "Held on"
    unread = 0
    harness = 0

    def __init__(self, root, given=""):
        self.root = root
        self.given = given

    @abc.abstractmethod
    def places(self):
        """The folders or files this member reads for this project, whether or not they are there."""
        raise NotImplementedError

    @abc.abstractmethod
    def conversations(self):
        """Every conversation found, oldest first, without opening one. Raises HistoryError where
        the place is not there or cannot be listed."""
        raise NotImplementedError

    @abc.abstractmethod
    def turns(self, conversation):
        """What was said, in order. Raises HistoryError where the conversation cannot be read."""
        raise NotImplementedError


class Harness(abc.ABC):
    """The program an agent runs in. Built from the environment a command was started in; a member
    reads that and nothing else, and never writes.

    `name` is what the owner is told it is; `residue` what the engine cannot do in it. `history` is
    the id of the history that reads the conversations it keeps, or an empty text. `forks`: it can
    start a copy of a running conversation that does one thing and ends.
    """

    id = ""
    name = ""
    residue = ""
    history = ""
    forks = False
    # Not so for the member that stands for every program the engine knows nothing of.
    known = True
    # Set in the environment of a copy of a conversation, to the name of the conversation it is a copy
    # of: what a copy reads back and notes belongs to that one, whatever the harness calls the copy.
    ORIGINAL = "VESTA_CONVERSATION"

    def __init__(self, environ):
        self.environ = environ

    @abc.abstractmethod
    def here(self):
        """Say whether this command was started from inside it."""
        raise NotImplementedError

    def conversation(self):
        """The name its history gives the conversation this command was started from, or an empty text."""
        return ""

    def fork(self, conversation, prompt, allowed, reads=False):
        """The command, as a list of arguments, that starts a copy of a conversation, gives it one
        instruction and ends. `allowed` are the commands the copy may run, each as the text it opens
        with; `reads` lets it read the project's files as well."""
        raise NotImplementedError

    def hook(self, command):
        """(the file the owner adds an entry to, the entry's text) for having `command` run each
        time the owner says something."""
        raise NotImplementedError

    def said(self, sent):
        """(the conversation, the owner's words) from what the harness sends a hook's command on standard input."""
        raise NotImplementedError

    def adopt(self, sent):
        """The environment a command would have been started in by this harness, where what was sent
        on standard input is this harness's own and names a conversation; else None."""
        return None


class Setting(abc.ABC):
    """One thing that differs by the person or the machine and never by the project: its answer is
    kept on this machine, outside what is committed.

    `asks` is the question in one line; `options` every answer as (value, what it means in one line).
    `default` is in effect while nothing was chosen and nothing found. `put`: a sheet puts the
    question to the owner while it is not chosen and more than one answer can take effect here.
    """

    id = ""
    asks = ""
    options = ()
    default = ""
    put = False

    def __init__(self, context):
        self.context = context

    def found(self, context):
        """The answer the engine can tell without asking, or an empty text."""
        return ""

    def effect(self, context, value):
        """(the answer in effect where `value` is the one chosen or found, why it differs or an empty text)."""
        return value, ""

    def turns_on(self, value):
        """The members an answer in effect adds for this person: {table: [ids]}."""
        return {}

    def after(self, context, value):
        """The lines to print once an answer was chosen: what else the owner has to do for it."""
        return []
