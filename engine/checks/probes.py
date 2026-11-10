"""The `probes` check: every probe reads, and no live trigger's probe fires unnoticed."""
from __future__ import annotations

from kernel import yamlsubset
from kernel.finding import ERROR, WARNING, Finding
from matchers import probes, triggers
from model.abstractions import Check, MatchError


class ProbesCheck(Check):
    id = "probes"
    residue = "not whether an `if` that has no probe holds; a probe is read from the files as they stand when the check runs"

    def run(self, context):
        found = []
        for store in context.stores.all():
            field = store.type.role_field("triggers")
            if field is None:
                continue
            for record in store.list():
                line = yamlsubset.line_of(record.front, (field,), 2)
                for trigger in record.mappings(field):
                    text = trigger.get("probe", "")
                    name = "%s/%s" % (record.label, trigger.get("id", ""))
                    if not isinstance(text, str) or not text.strip():
                        continue
                    try:
                        probes.parse(text, context)
                    except MatchError as error:
                        found.append(Finding(ERROR, self.id, record.path, line, "the probe of %s does not read: %s" % (name, error)))
                        continue
                    if trigger.get("resolved") or not store.type.is_accepted(record):
                        continue
                    state = probes.evaluate(text, context)
                    if state.state == probes.FIRED:
                        found.append(Finding(
                            WARNING, self.id, record.path, line,
                            "the probe of the live trigger %s fires: its condition holds in the project now. Act on the trigger, or resolve it through a `resolve-trigger` proposal" % name,
                        ))
                    elif state.state == probes.ERROR:
                        found.append(Finding(WARNING, self.id, record.path, line, "the probe of %s cannot be evaluated: %s" % (name, state.reason)))
        return found


MEMBER = ProbesCheck
