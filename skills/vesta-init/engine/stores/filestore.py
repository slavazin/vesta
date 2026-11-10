"""The file-backed store: one folder of record files, in one of two layouts."""
from __future__ import annotations

from kernel import frontmatter, ids, markdown, yamlsubset
from kernel.errors import Refusal, SubsetError
from kernel.finding import ERROR
from model.abstractions import Store
from model.record import LABEL, UID, Problem, Record

RESERVED = ("readme.md", "schema.md", "index.md")
OPEN = "open"
ARCHIVE = "archive"
LEDGER = "ledger"
RECORD_DEPTH = 3


def is_record_name(name):
    """A record file is `<label>.md`; a name with a second dot, as a draft's, is not one."""
    return name.endswith(".md") and name.lower() not in RESERVED and "." not in name[:-3]


class FileStore(Store):
    """A store over a Tree. `settings` is the store's configuration entry; `type` its record type."""

    def __init__(self, settings, record_type, tree, clock):
        self.settings = settings
        self.name = settings.name
        self.path = settings.path
        self.type = record_type
        self.tree = tree
        self.clock = clock
        self._scan = None

    # --------------------------------------------------------------------------------------- reading

    def folders(self):
        """The folders the store's layout has from the first day."""
        if self.type.layout == "open-archive":
            return [self.path, self.path + "/" + OPEN, self.path + "/" + ARCHIVE]
        return [self.path]

    def paths(self):
        """The path of every record file, sorted."""
        folders = [self.path]
        if self.type.layout == "open-archive":
            folders = [self.path + "/" + OPEN]
            archive = self.path + "/" + ARCHIVE
            folders += [archive + "/" + name for name in self.tree.list(archive) if self.tree.is_dir(archive + "/" + name)]
        found = []
        for folder in folders:
            for name in self.tree.list(folder):
                if is_record_name(name) and self.tree.is_file(folder + "/" + name):
                    found.append(folder + "/" + name)
        return sorted(found)

    def read(self, path):
        """The record at a path. Raises SubsetError where its frontmatter does not read."""
        text = self.tree.read(path)
        front, body, body_line = frontmatter.split(text, path)
        fields = yamlsubset.read(front, path, 2, depth=RECORD_DEPTH)
        return Record(self.name, path, fields, body, front, body_line)

    def scan(self):
        """[(path, record or None, problems)] for every record file; a file that does not read has
        no record. Read once for each store object; a write through the store reads again."""
        if self._scan is None:
            found = []
            for path in self.paths():
                try:
                    found.append((path, self.read(path), []))
                except SubsetError as error:
                    found.append((path, None, [Problem(ERROR, error.line, error.message)]))
                except UnicodeDecodeError:
                    found.append((path, None, [Problem(ERROR, 1, "the file is not UTF-8 text")]))
            self._scan = found
        return self._scan

    def unread(self):
        """The paths of the record files that do not read."""
        return [path for path, record, _ in self.scan() if record is None]

    def list(self):
        records = [record.copy() for _, record, _ in self.scan() if record is not None]
        return sorted(records, key=lambda record: ids.sort_key(record.label))

    def get(self, ref):
        """The record named. An internal id is followed where the name has one; the label is used
        only where it has none."""
        label, uid = ids.parse_ref(ref)
        for record in self.list():
            if (uid is not None and record.uid == uid) or (uid is None and label and record.label == label):
                return record
        return None

    def locate(self, ref):
        record = self.get(ref)
        return None if record is None else record.path

    def title(self, record):
        return markdown.Document(record.body).title or ""

    # --------------------------------------------------------------------------------------- writing

    def path_for(self, label, folder=None):
        """Where a record of that label lives; in the open-archive layout, under `open/` unless told."""
        if self.type.layout == "open-archive":
            return "%s/%s/%s.md" % (self.path, folder or OPEN, label)
        return "%s/%s.md" % (self.path, label)

    def text(self, record):
        """The file text of a record in the canonical form."""
        body = record.body if record.body.endswith("\n") or not record.body else record.body + "\n"
        return frontmatter.join(yamlsubset.write(self.type.front(record)), body)

    def write(self, record, relabel=False):
        """Write a record at its own place in the store. In a ledger, refuses a change to a field
        not marked mutable; `relabel` lets the label change, and nothing else."""
        rule = "%s/SCHEMA.md, Fields" % self.path
        for name in record.fields:
            if self.type.field(name) is None:
                raise Refusal("`%s` is not a field of the store `%s`; the record was not written" % (name, self.name), rule)
        if not record.label or not is_record_name(record.label + ".md") or "/" in record.label:
            raise Refusal("`%s` cannot label a record; the record was not written" % record.label, rule)
        before = self._held(record.uid) if self.settings.kind == LEDGER else None
        if self.settings.kind == LEDGER:
            if before is not None:
                was, now = self.type.front(before), self.type.front(record)
                for field in self.type.fields:
                    if field.mutable or (relabel and field.name == LABEL):
                        continue
                    if was.get(field.name) != now.get(field.name):
                        raise Refusal(
                            "the field `%s` of %s is fixed once the record is written, so the record was not changed. "
                            "What a record of this store says is changed by replacing it with a successor (a `supersede` proposal)"
                            % (field.name, before.label),
                            rule,
                        )
        if not record.path:
            record.path = self.path_for(record.label)
        if record.path not in self._places(record.label):
            raise Refusal(
                "%s is not where the store `%s` keeps a record labelled %s; the record was not written" % (record.path, self.name, record.label),
                "%s/README.md" % self.path,
            )
        if self.settings.kind == LEDGER:
            if self.tree.is_file(record.path) and (before is None or before.path != record.path):
                raise Refusal(
                    "%s already holds another record, or a file that does not read; a file in this store is never written over" % record.path,
                    "%s/README.md" % self.path,
                )
        self.tree.write(record.path, self.text(record))
        self._scan = None
        return record.path

    def _places(self, label):
        """The paths at which a record of that label may live."""
        if self.type.layout != "open-archive":
            return [self.path_for(label)]
        archive = self.path + "/" + ARCHIVE
        folders = [OPEN] + [ARCHIVE + "/" + name for name in self.tree.list(archive)]
        return [self.path_for(label, folder) for folder in folders]

    def _held(self, uid):
        for record in self.list():
            if record.uid == uid:
                return record
        return None

    def next_id(self, seed, also=()):
        records = self.list()
        uid = ids.new_uid(self.name, self.clock.timestamp(), seed, [record.uid for record in records])
        if self.settings.digits > 0:
            used = [record.label for record in records] + list(also)
            label = ids.numbered_label(self.settings.prefix, self.settings.digits, ids.next_number(used, self.settings.prefix))
        else:
            label = ids.dated_label(self.settings.prefix, self.clock.today(), uid)
        return uid, label
