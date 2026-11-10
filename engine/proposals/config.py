"""The `config` kind: keys of the configuration rewritten. Where a store's label setting changes,
the store's records are renamed in the same change."""
from __future__ import annotations

from kernel import yamlsubset
from kernel.errors import SubsetError
from model import config as configuration
from model.abstractions import Change, KindError, ProposalKind
from proposals import blocks, edits, relabel, targets


def _set(data, dotted, value):
    """Set a dotted key in nested mappings. Returns the value that was there, or None."""
    parts = dotted.split(".")
    here = data
    for part in parts[:-1]:
        if not isinstance(here.get(part), dict):
            if part in here:
                raise KindError("`%s` is not a mapping, so `%s` cannot be set under it" % (part, dotted))
            here[part] = {}
        here = here[part]
    old = here.get(parts[-1])
    here[parts[-1]] = value
    return old


class ConfigKind(ProposalKind):
    id = "config"

    def resolve(self, target, context):
        return targets.config_file(context, target)

    def scaffold(self, target, context, label):
        return "```%s\n%s the keys to set as dotted paths, as `reminders.learn.open-observations: 40`>\n```" % (blocks.SET, blocks.FILL)

    def _data(self, proposal, context):
        values = blocks.dotted_block(proposal.change())
        try:
            data = yamlsubset.read(context.tree.read(configuration.PATH), configuration.PATH)
        except SubsetError as error:
            raise KindError("%s does not read: %s" % (configuration.PATH, error))
        replaced = []
        for dotted, value in values.items():
            old = _set(data, dotted, value)
            replaced.append(("%s, `%s`" % (configuration.PATH, dotted), "(not set)" if old is None else edits.show(old)))
        return data, replaced

    def validate(self, proposal, context):
        return edits.problems(lambda: self._data(proposal, context))

    def changes(self, proposal, context, approver):
        data, replaced = self._data(proposal, context)
        change = Change(configuration.PATH[len("vesta/"):])
        change.replaced = replaced
        change.writes[configuration.PATH] = yamlsubset.write(data)
        after = configuration.Config(data)
        for name, settings in after.stores.items():
            before = context.config.stores.get(name)
            store = context.stores.get(name)
            if before is None or store is None or (before.prefix, before.digits) == (settings.prefix, settings.digits):
                continue
            renamed = relabel.plan(context, store, settings.prefix, settings.digits)
            relabel.into(change, context, renamed)
        return change

    def standing_cost(self, target, context):
        return "none"


MEMBER = ConfigKind
