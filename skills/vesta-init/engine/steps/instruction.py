"""The instruction text of a step: shipped beside the steps as `text/<step id>.md`.

A text names record fields and stores through words in braces, which are filled from the project's own
configuration and schemas when the sheet is printed. A paragraph that opens `[quiet]`, `[standard]`
or `[active]` is printed only at that engagement level.
"""
from __future__ import annotations

import os
import re

from model.abstractions import ROLES

FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "text")
LEVEL = re.compile(r"\[(quiet|standard|active)\]\s*")


def read(name):
    """The shipped text of that name, or None where the engine ships none."""
    path = os.path.join(FOLDER, name + ".md")
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as handle:
        return handle.read().decode("utf-8").replace("\r\n", "\n")


def _names(values):
    values = list(dict.fromkeys(values))
    return " or ".join("`%s`" % value for value in values)


def common_words(context):
    """The words every text may use: the recalled stores, and the field each index role is played by."""
    stores = context.stores.recalled()
    words = {"stores": _names(store.name for store in stores) or "no store"}
    for role in ROLES:
        fields = [store.type.role_field(role) for store in stores if store.type.role_field(role)]
        words[role] = _names(fields) or "`%s`" % role
    words["level"] = context.config.engagement
    words["session"] = context.session.id if context.session is not None else "<session id>"
    return words


def fill(text, context, words=None):
    """A text with its level paragraphs chosen and its words filled."""
    kept = []
    for paragraph in text.strip().split("\n\n"):
        found = LEVEL.match(paragraph)
        if found:
            if found.group(1) != context.config.engagement:
                continue
            paragraph = paragraph[found.end():]
        kept.append(" ".join(line.strip() for line in paragraph.split("\n")) if not paragraph.lstrip().startswith("- ") else paragraph)
    result = "\n\n".join(kept)
    filled = common_words(context)
    filled.update(words or {})
    for name, value in filled.items():
        result = result.replace("{%s}" % name, value)
    return result


def of_step(context, step_id, words=None):
    """The instruction of a step. `<step id>.md` serves every checkpoint; a checkpoint whose walk
    asks something else of the step has `<step id>.<checkpoint id>.md` beside it."""
    checkpoint = getattr(getattr(context.walk, "checkpoint", None), "id", None)
    text = read("%s.%s" % (step_id, checkpoint)) if checkpoint else None
    if text is None:
        text = read(step_id)
    if text is None:
        return "This engine ships no instruction for the step `%s`." % step_id
    return fill(text, context, words)
