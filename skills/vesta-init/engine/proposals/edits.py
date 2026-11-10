"""What the kinds that rewrite fields of a record share: the `vesta-set` block applied to one record."""
from __future__ import annotations

from kernel import yamlsubset
from model.abstractions import Change, KindError
from proposals import blocks


def show(value):
    """A field's value as one line of text, for the record of what was replaced."""
    if isinstance(value, (list, dict)):
        return " ".join(yamlsubset.write({"was": value}).split())[len("was: "):] or "[]"
    return str(value) if value != "" else "(empty)"


def named(proposal, allowed, what):
    """The fields a proposal's `vesta-set` block names, each one the kind allows. Raises KindError."""
    values = blocks.set_block(proposal.change())
    for name in values:
        if name not in allowed:
            raise KindError("the `vesta-set` block names `%s`; %s: %s" % (name, what, ", ".join("`%s`" % item for item in allowed) or "none"))
    return values


def rewritten(store, record, values):
    """The Change that gives a record's fields their new values."""
    changed = record.copy()
    change = Change(record.ref)
    for name, value in values.items():
        field = store.type.field(name)
        if field is None:
            raise KindError("`%s` is not a field of the store `%s`" % (name, store.name))
        if store.settings.kind == "ledger" and not field.mutable:
            raise KindError("`%s` is fixed once a record of the store `%s` is written; it changes only through a successor" % (name, store.name))
        change.replaced.append(("%s, `%s`" % (record.label, name), show(record.get(name, field.empty()))))
        changed.fields[name] = value
    change.writes[record.path] = store.text(changed)
    return change


def problems(check):
    """A kind's `validate`, from a function that raises KindError."""
    try:
        check()
    except KindError as error:
        return [str(error)]
    return []
