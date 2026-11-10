"""The exceptions the engine raises on purpose. The command line turns each into an exit code."""
from __future__ import annotations


class SubsetError(Exception):
    """A text the codec refuses, with the file and line that hold the refused construct."""

    def __init__(self, file, line, message):
        super().__init__("%s:%d: %s" % (file or "<text>", line, message))
        self.file = file
        self.line = line
        self.message = message


class Refusal(Exception):
    """A command that would break a rule. `rule` names the file and section that states the rule."""

    def __init__(self, message, rule=""):
        super().__init__(message)
        self.message = message
        self.rule = rule


class UsageError(Exception):
    """A command line or a configuration the engine cannot act on."""
