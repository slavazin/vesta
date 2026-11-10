"""The `lengths` check: lines an index prints at every start stay short."""
from __future__ import annotations

from kernel import yamlsubset
from kernel.finding import WARNING, Finding
from model.abstractions import Check

LIMITS = (("when", 300), ("why", 200), ("except", 200))
TITLE = 160


class LengthsCheck(Check):
    id = "lengths"
    residue = "length only: not whether a line is clear"

    def run(self, context):
        found = []
        for store in context.stores.all():
            for record in store.list():
                for role, limit in LIMITS:
                    name = store.type.role_field(role)
                    value = record.get(name) if name else ""
                    if isinstance(value, str) and len(value) > limit:
                        found.append(Finding(
                            WARNING, self.id, record.path, yamlsubset.line_of(record.front, (name,), 2),
                            "the `%s` line is %d characters; keep it to %d" % (name, len(value), limit),
                        ))
                title = store.title(record)
                if len(title) > TITLE:
                    found.append(Finding(WARNING, self.id, record.path, record.body_line, "the title is %d characters; keep it to %d" % (len(title), TITLE)))
        return found


MEMBER = LengthsCheck
