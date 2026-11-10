"""A proposal as the appliers and the checks read it: its fields, its sections, its draft, its kind."""
from __future__ import annotations

from kernel import frontmatter, ids, markdown, yamlsubset
from kernel.errors import Refusal, SubsetError, UsageError
from model.abstractions import (
    APPROVED_BY, DECIDED, DISPOSITION, OPEN, OUTCOME, STATUS, ACCEPTED, KindError,
)
from model.record import LABEL, UID, Record
from proposals import blocks
from session import observations, pending
from stores import conditions
from stores.filestore import RECORD_DEPTH

LOG = pending.LOG
TABLE = "kinds"
CHANGE = "Change"
REPLACED = "Replaced"
DRAFT = pending.DRAFT
NEW = ids.NEW
PLACEHOLDER_UID = "00000000"
RULE = "%s/SCHEMA.md, Kinds"
KINDS_RULE = "vesta/vesta.yml, `proposals.kinds`"


class Proposal(object):
    """One proposal: its store, its record, and what its body holds."""

    def __init__(self, store, record):
        self.store = store
        self.record = record
        self.document = markdown.Document(record.body)

    label = property(lambda self: self.record.label)
    ref = property(lambda self: self.record.ref)
    kind = property(lambda self: str(self.record.get(pending.KIND)))
    target = property(lambda self: str(self.record.get(pending.TARGET)))
    evidence = property(lambda self: self.record.texts(pending.EVIDENCE))
    title = property(lambda self: self.store.title(self.record))
    draft_path = property(lambda self: self.record.path[:-len(".md")] + DRAFT)

    def change(self):
        """The text of the Change section; empty where there is none."""
        section = self.document.section(CHANGE)
        return "" if section is None else self.document.text_of(section)


def kind_of(context, name):
    """The kind of that id, where the configuration enables it and the engine has it. Raises Refusal."""
    if name not in context.config.kinds and name not in context.known.get(TABLE, ()):
        raise UsageError("`%s` is not a kind of proposal; the kinds enabled in this project are: %s" % (name, ", ".join(context.config.kinds) or "none"))
    if name not in context.config.kinds:
        raise Refusal(
            "the kind `%s` is not enabled in this project, so a proposal of it can be neither drafted nor applied; the kinds enabled are: %s"
            % (name, ", ".join(context.config.kinds) or "none"), KINDS_RULE,
        )
    if name not in context.known.get(TABLE, ()):
        raise UsageError("this engine has no proposal kind `%s`; `check` says more" % name)
    return context.member(TABLE, name)()


def labels_used(context, store):
    """Every label a proposal has had: the pending ones and the decided ones in the log."""
    used = [record.label for record in store.list()]
    for name in context.tree.list(LOG):
        if name.endswith(".md") and not name.endswith(DRAFT):
            used.append(name[:-len(".md")])
    return used


def find(context, name):
    """The pending proposal a label or an internal id names. Raises Refusal for one already decided."""
    label = ids.parse_ref(name)[0] or name
    for store in pending.stores_of(context):
        record = store.get(name)
        if record is not None:
            if store.type.life(record, OUTCOME):
                raise Refusal("%s is already decided: %s. Nothing was changed." % (record.label, store.type.life(record, OUTCOME)), "vesta/INTERNALS.md, How changes are made")
            return Proposal(store, record)
    if context.tree.is_file("%s/%s.md" % (LOG, label)):
        raise Refusal("%s is already decided; it is in %s/%s.md. Nothing was changed." % (label, LOG, label), "vesta/INTERNALS.md, How changes are made")
    waiting = ", ".join(record.label for _, record in pending.pending(context)) or "none"
    raise UsageError("`%s` names no proposal that is waiting; the ones waiting are: %s" % (name, waiting))


def evidence_records(context, refs):
    """([(store, record)] for the evidence that resolves to an observation, [the refs that do not])."""
    found, lost = [], []
    takers = observations.stores_of(context)
    for ref in refs:
        named = context.stores.resolve(ref)
        if named is None or named[0] not in takers:
            lost.append(ref)
        else:
            found.append(named)
    return found, lost


def sessions_of(context, refs):
    """How many separate sessions the evidence comes from."""
    found, _ = evidence_records(context, refs)
    return len(set(str(record.get(observations.SESSION)) for _, record in found))


# ------------------------------------------------------------------------------------------- drafts

def read_draft(context, proposal, store):
    """The draft of a proposal as a record of the target store, not yet placed. Raises KindError."""
    path = proposal.draft_path
    if not context.tree.is_file(path):
        raise KindError("%s is missing: a `%s` proposal has the full text of its record there" % (path, proposal.kind))
    try:
        front, body, body_line = frontmatter.split(context.tree.read(path), path)
        fields = yamlsubset.read(front, path, 2, depth=RECORD_DEPTH)
    except (SubsetError, UnicodeDecodeError) as error:
        raise KindError("%s does not read: %s" % (path, error))
    return Record(store.name, path, fields, body, front, body_line)


def placed(context, store, draft, approver, uid=None, label=None):
    """A draft as the record it becomes: its placeholders filled and its place in the store set.
    With no id given, placeholder ids stand in, as when a draft is only being checked."""
    record = draft.copy()
    kind = store.type
    record.fields[UID] = uid or PLACEHOLDER_UID
    record.fields[LABEL] = label or ids.numbered_label(store.settings.prefix, max(store.settings.digits, 1), ids.next_number([r.label for r in store.list()], store.settings.prefix))
    for role, value in ((DECIDED, context.clock.today()), (APPROVED_BY, approver), (STATUS, ACCEPTED)):
        if kind.life_field(role):
            record.fields[kind.life_field(role)] = value
    record.path = store.path_for(record.fields[LABEL])
    return record


def draft_problems(context, proposal, store, approver="the approver"):
    """What is wrong with a draft, as sentences."""
    try:
        draft = read_draft(context, proposal, store)
    except KindError as error:
        return [str(error)]
    found = []
    for name in (UID, LABEL):
        if draft.get(name) != NEW:
            found.append("the draft's `%s` must be `%s`; the engine assigns it on approval" % (name, NEW))
    record = placed(context, store, draft, approver)
    found.extend("the draft: %s" % problem.message for problem in conditions.problems(record, store, context))
    if blocks.FILL in context.tree.read(proposal.draft_path):
        found.append("%s still holds a `%s …>` placeholder" % (proposal.draft_path, blocks.FILL))
    return found


# ------------------------------------------------------------------------------------------- checks

def problems(context, proposal):
    """Everything wrong with a pending proposal as drafted, as sentences."""
    found = []
    record = proposal.record
    name = proposal.kind
    if name not in context.config.kinds:
        return ["its kind `%s` is not enabled in `proposals.kinds`" % name]
    if name not in context.known.get(TABLE, ()):
        return ["its kind `%s` is not one this engine has" % name]
    kind = context.member(TABLE, name)()
    _, lost = evidence_records(context, proposal.evidence)
    for ref in lost:
        found.append("`%s` names %s, which is not an observation" % (pending.EVIDENCE, ref))
    counted = sessions_of(context, proposal.evidence)
    if record.get(pending.SESSIONS) != counted:
        found.append("`%s` is %s; the evidence comes from %d session%s, and the engine computes this figure" % (
            pending.SESSIONS, record.get(pending.SESSIONS), counted, "" if counted == 1 else "s"))
    if blocks.FILL in record.body:
        found.append("it still holds a `%s …>` placeholder" % blocks.FILL)
    has_draft = context.tree.is_file(proposal.draft_path)
    if has_draft and not kind.draft:
        found.append("%s is there, and a `%s` proposal has no draft" % (proposal.draft_path, name))
    try:
        kind.resolve(proposal.target, context)
    except KindError as error:
        return found + ["`%s`: %s" % (pending.TARGET, error)]
    found.extend(kind.validate(proposal, context))
    return found


def overtaken(context, proposal):
    """Why the change a waiting proposal describes can no longer be made at all, or an empty text.
    A proposal that only needs correcting as drafted is not overtaken."""
    name = proposal.kind
    if name not in context.config.kinds:
        return "its kind `%s` is no longer enabled" % name
    if name not in context.known.get(TABLE, ()):
        return ""
    try:
        context.member(TABLE, name)().resolve(proposal.target, context)
    except KindError as error:
        return str(error)
    return ""


def checked(context, proposal):
    """Refuse a proposal that cannot be applied as drafted."""
    found = problems(context, proposal)
    if found:
        raise Refusal(
            "%s cannot be applied as drafted:\n%s\nNothing was changed. Correct the proposal and run the command again."
            % (proposal.label, "\n".join("- " + line for line in found)),
            RULE % proposal.store.path,
        )
