"""The `records` check: every record of every store against its schema block and conditions."""
from __future__ import annotations

from kernel import ids, yamlsubset
from kernel.finding import ERROR, WARNING, Finding
from stores import conditions
from model.abstractions import OUTCOME, Check
from proposals import proposal as proposals
from model.record import LABEL, UID


class RecordsCheck(Check):
    id = "records"
    residue = (
        "not whether a record is true, well anchored, or recognizable by its `when` line; "
        "`falsifier-or-trigger` reads that one is present, not whether it could ever happen"
    )

    def run(self, context):
        found = []
        seen = {}
        for name, problems in sorted(context.stores.unreadable.items()):
            settings = context.config.stores[name]
            found.append(Finding(
                ERROR, self.id, settings.path + "/SCHEMA.md", problems[0][0] if problems else 1,
                "the records of the store `%s` were not checked: its SCHEMA.md %s" % (name, "does not read" if problems else "is missing"),
            ))
        for store in context.stores.all():
            labels = {}
            for message in conditions.unknown(store.type):
                found.append(Finding(ERROR, self.id, store.path + "/SCHEMA.md", 1, message))
            for path, record, problems in store.scan():
                for problem in problems:
                    found.append(Finding(problem.severity, self.id, path, problem.line, problem.message))
                if record is None:
                    continue
                found.extend(self._one(context, store, record))
                if record.uid:
                    seen.setdefault(record.uid, []).append(record)
                if record.label:
                    labels.setdefault(record.label, []).append(record)
            for label, records in sorted(labels.items()):
                records.sort(key=lambda record: (not record.path.endswith("/" + label + ".md"), record.path))
                for record in records[1:]:
                    found.append(Finding(
                        ERROR, self.id, record.path, yamlsubset.line_of(record.front, (LABEL,), 2),
                        "two records of `%s` are labelled %s (the other is %s); run `relabel %s --one %s` to move this one to the next free number"
                        % (store.name, label, records[0].path, store.name, record.ref),
                    ))
        for uid, records in sorted(seen.items()):
            for record in records[1:]:
                found.append(Finding(
                    ERROR, self.id, record.path, yamlsubset.line_of(record.front, (UID,), 2),
                    "the internal id %s is also that of %s; an internal id belongs to one record" % (uid, records[0].path),
                ))
        return found

    def _one(self, context, store, record):
        found = [Finding(p.severity, self.id, record.path, p.line, p.message) for p in store.type.validate(record)]
        if not found:
            for condition, argument in conditions.usable(store.type):
                for p in condition(record, store, context, argument):
                    found.append(Finding(p.severity, self.id, record.path, p.line, p.message))
        if not found and record.label and not self._label_fits(store, record):
            found.append(Finding(
                ERROR, self.id, record.path, yamlsubset.line_of(record.front, (LABEL,), 2),
                "the label `%s` is not in the form this store's records take, as `%s`" % (record.label, self._example(store)),
            ))
        try:
            front = store.type.front(record)
            # A field the schema gained after the record was written, and does not require, may be absent.
            older = dict((name, value) for name, value in front.items() if name in record.fields or getattr(store.type.field(name), "required", False))
            canonical = record.front in (yamlsubset.write(front), yamlsubset.write(older))
        except ValueError:
            canonical = True
        if not canonical and not any(f.severity == ERROR for f in found):
            found.append(Finding(
                WARNING, self.id, record.path, 2,
                "the frontmatter is not in the written form; the engine rewrites it the next time it writes this record",
            ))
        found.extend(self._stale_refs(context, store, record))
        if store.type.life_field(OUTCOME) is not None and not store.type.life(record, OUTCOME) and not any(f.severity == ERROR for f in found):
            for message in proposals.problems(context, proposals.Proposal(store, record)):
                found.append(Finding(ERROR, self.id, record.path, 1, "the proposal cannot be applied as drafted: %s" % message))
        return found

    def _label_fits(self, store, record):
        settings = store.settings
        if settings.digits > 0:
            number = ids.number_of(record.label, settings.prefix)
            return number is not None and len(record.label) - len(settings.prefix) - 1 >= settings.digits
        return record.label.startswith(settings.prefix + "-") and record.label.endswith("-" + record.uid)

    def _example(self, store):
        settings = store.settings
        if settings.digits > 0:
            return ids.numbered_label(settings.prefix, settings.digits, 1)
        return "%s-<date>-<internal id>" % settings.prefix

    def _stale_refs(self, context, store, record):
        found = []
        for field in store.type.fields:
            if field.type not in ("ref", "refs"):
                continue
            for text in record.texts(field.name):
                label, uid = ids.parse_ref(text)
                if uid is None or label is None:
                    continue
                target = context.stores.resolve(uid)
                if target is not None and target[1].label != label:
                    found.append(Finding(
                        WARNING, self.id, record.path, yamlsubset.line_of(record.front, (field.name,), 2),
                        "`%s` names %s, which is now labelled %s; the engine refreshes the label the next time it writes this record"
                        % (field.name, text, target[1].label),
                    ))
        return found


MEMBER = RecordsCheck
