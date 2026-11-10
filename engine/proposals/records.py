"""What the kinds that write a new record share: the draft's starting text, and the successor."""
from __future__ import annotations

from kernel import frontmatter, ids, yamlsubset
from model.abstractions import (
    ACCEPTED, APPROVED_BY, DECIDED, STATUS, SUPERSEDED, SUPERSEDED_BY, SUPERSEDES, Change, KindError,
)
from model.record import LABEL, UID, Record
from proposals import blocks, proposal as proposals

SEE = "See %s"


def see(label):
    return SEE % (label + proposals.DRAFT)


def skeleton(store, replaces=(), source=None):
    """The text a draft starts with: every field of the store's schema, the engine's own left for
    the engine, and each section the schema names. With a source, that record's own text."""
    kind = store.type
    engine = [UID, LABEL] + [kind.life_field(role) for role in (DECIDED, APPROVED_BY)]
    cleared = [kind.life_field(role) for role in (SUPERSEDED_BY,)]
    record = source.copy() if source is not None else Record(store.name, "", {}, "")
    fields = kind.front(record)
    for field in kind.fields:
        if field.name in (UID, LABEL):
            fields[field.name] = ids.NEW
        elif field.name in engine or field.name in cleared:
            fields[field.name] = field.empty()
        elif field.name == kind.life_field(STATUS):
            fields[field.name] = ACCEPTED
        elif field.name == kind.life_field(SUPERSEDES):
            fields[field.name] = [item.ref for item in replaces]
        elif source is None and field.required and field.type == "text":
            fields[field.name] = "%s %s>" % (blocks.FILL, field.name)
    if source is not None:
        body = source.body
    else:
        body = "# %s the title: one line stating what is decided>\n" % blocks.FILL
        for name, required in kind.sections:
            body += "\n## %s\n%s %s>\n" % (name, blocks.FILL, "this section" if required else "this section, or delete it")
    return frontmatter.join(yamlsubset.write(fields), body)


def names_draft(proposal):
    """What is wrong with a Change section that should point at the draft."""
    wanted = see(proposal.label)
    return [] if wanted in proposal.change() else ["the Change section says `%s` and nothing else" % wanted]


def replaces_problems(context, proposal, store, targets):
    """What is wrong where a draft does not name every record it replaces, and only those."""
    field = store.type.life_field(SUPERSEDES)
    if field is None:
        return ["the store `%s` has no field for what a record replaces, so its records cannot be replaced" % store.name]
    try:
        draft = proposals.read_draft(context, proposal, store)
    except KindError:
        return []
    named = set(ids.parse_ref(text)[1] or ids.parse_ref(text)[0] for text in draft.texts(field))
    wanted = set(item.uid for item in targets)
    labels = dict((item.label, item.uid) for item in targets)
    named = set(labels.get(name, name) for name in named)
    if named != wanted:
        return ["the draft's `%s` must name exactly: %s" % (field, ", ".join(item.ref for item in targets))]
    return []


def successor(context, proposal, store, approver, targets=()):
    """The Change that writes a draft as a record and flips each record it replaces."""
    draft = proposals.read_draft(context, proposal, store)
    uid, label = store.next_id(store.title(draft))
    record = proposals.placed(context, store, draft, approver, uid, label)
    kind = store.type
    if targets:
        record.fields[kind.life_field(SUPERSEDES)] = [item.ref for item in targets]
    change = Change(record.ref, created=True)
    change.writes[record.path] = store.text(record)
    for target in targets:
        flipped = target.copy()
        change.replaced.append(("%s, `%s`" % (target.label, kind.life_field(STATUS)), str(kind.life(target, STATUS))))
        flipped.fields[kind.life_field(STATUS)] = SUPERSEDED
        if kind.life_field(SUPERSEDED_BY) is None:
            raise KindError("the store `%s` has no field for what replaced a record" % store.name)
        flipped.fields[kind.life_field(SUPERSEDED_BY)] = record.ref
        change.writes[target.path] = store.text(flipped)
    return change


def cost(store):
    if store.settings.recall == "index":
        return "one short block more read at every start"
    return "none: the store `%s` is not read at the start" % store.name
