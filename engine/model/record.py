"""The record: one entry of a store, as read from its file."""
from __future__ import annotations

from kernel import ids

UID = "uid"
LABEL = "id"


class Problem(object):
    """Something wrong with a file, before a check turns it into a finding."""

    __slots__ = ("severity", "line", "message")

    def __init__(self, severity, line, message):
        self.severity = severity
        self.line = line
        self.message = message

    def __repr__(self):
        return "Problem(%s, %d, %r)" % (self.severity, self.line, self.message)


class Record(object):
    """A record: its store, its file, its frontmatter fields and its body.

    `fields` holds what the frontmatter holds, by field name. `front` is the frontmatter text and
    `body_line` the 1-based line of the file on which the body starts, both for naming a line in a
    finding.
    """

    def __init__(self, store, path, fields, body, front="", body_line=1):
        self.store = store
        self.path = path
        self.fields = fields
        self.body = body
        self.front = front
        self.body_line = body_line

    @property
    def uid(self):
        value = self.fields.get(UID, "")
        return value if isinstance(value, str) else ""

    @property
    def label(self):
        value = self.fields.get(LABEL, "")
        return value if isinstance(value, str) else ""

    @property
    def ref(self):
        """`<label>@<uid>`: how another record, a log line or the engine's state names this one."""
        return ids.format_ref(self.label, self.uid)

    def get(self, name, default=""):
        return self.fields.get(name, default)

    def texts(self, name):
        """A list field's items as text. An empty string stands for an empty list."""
        value = self.fields.get(name, [])
        if isinstance(value, str):
            return [value] if value else []
        if isinstance(value, (list, tuple)):
            return [item for item in value if isinstance(item, str)]
        return []

    def mappings(self, name):
        """A list field's items that are mappings."""
        value = self.fields.get(name, [])
        return [item for item in value if isinstance(item, dict)] if isinstance(value, (list, tuple)) else []

    def copy(self):
        fields = {}
        for name, value in self.fields.items():
            if isinstance(value, list):
                value = [dict(item) if isinstance(item, dict) else item for item in value]
            fields[name] = value
        return Record(self.store, self.path, fields, self.body, self.front, self.body_line)
