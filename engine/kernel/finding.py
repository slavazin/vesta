"""The finding: one thing a check reports."""
from __future__ import annotations

ERROR = "error"
WARNING = "warning"


class Finding(object):
    """One finding of one check, printed as `<severity> <check id> <file>:<line> <message>`."""

    __slots__ = ("severity", "check", "file", "line", "message")

    def __init__(self, severity, check, file, line, message):
        if severity not in (ERROR, WARNING):
            raise ValueError("a finding is an error or a warning, not %r" % (severity,))
        self.severity = severity
        self.check = check
        self.file = file
        self.line = line
        self.message = message

    def key(self):
        """What makes two findings the same finding."""
        return (self.severity, self.check, self.file, self.message)

    def render(self):
        return "%s %s %s:%d %s" % (self.severity, self.check, self.file, self.line, self.message)

    def __eq__(self, other):
        return isinstance(other, Finding) and self.render() == other.render()

    def __hash__(self):
        return hash(self.render())

    def __repr__(self):
        return "Finding(%s)" % self.render()
