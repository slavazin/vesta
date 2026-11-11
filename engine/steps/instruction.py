"""The instruction text of a step: shipped beside the steps as `text/<step id>.md`.

A text names record fields and stores through words in braces, which are filled from the project's own
configuration and schemas when the sheet is printed. A paragraph that opens `[quiet]`, `[standard]`
or `[active]` is printed only at that engagement level. One that opens `[<setting>: <answer>]`, or
with several answers between commas, is printed only where that answer of the setting is in effect on
this machine: the text of the other answers is never printed, so nobody reads it. Where the setting
is one whose question is still to be put to the owner, the question follows the text, once a sheet.
"""
from __future__ import annotations

import os
import re

from kernel.errors import UsageError
from model.abstractions import ROLES
from session import asides, settings

FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "text")
LEVEL = re.compile(r"\[(quiet|standard|active)\]\s*")
WHERE = re.compile(r"\[([a-z][a-z-]*): ([a-z][a-z-]*(?:, [a-z][a-z-]*)*)\]\s*")


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


def conditions(text):
    """Every (setting, [answers]) a text makes a paragraph depend on."""
    found = []
    for paragraph in text.strip().split("\n\n"):
        while True:
            level, where = LEVEL.match(paragraph), WHERE.match(paragraph)
            if where:
                found.append((where.group(1), where.group(2).split(", ")))
            if not (level or where):
                break
            paragraph = paragraph[(level or where).end():]
    return found


def _resolved(context, name, cache):
    """(a setting as it stands, why what was chosen for it could not be read or an empty text)."""
    if name not in cache:
        try:
            cache[name] = (settings.resolve(context, name), "")
        except UsageError as error:
            # What was chosen cannot be read: the text of the answer that holds with nothing chosen is printed, and the sheet says so.
            cache[name] = (settings.resolve(context, name, {}), str(error))
    return cache[name]


def fill(text, context, words=None):
    """A text with its level paragraphs and its setting paragraphs chosen and its words filled."""
    kept, cache, asked = [], {}, []
    for paragraph in text.strip().split("\n\n"):
        printed = True
        while printed:
            level, where = LEVEL.match(paragraph), WHERE.match(paragraph)
            if level:
                printed = level.group(1) == context.config.engagement
            elif where:
                resolved, _ = _resolved(context, where.group(1), cache)
                printed = resolved.effect in where.group(2).split(", ")
                if where.group(1) not in asked:
                    asked.append(where.group(1))
            else:
                break
            paragraph = paragraph[(level or where).end():]
        if printed:
            kept.append(" ".join(line.strip() for line in paragraph.split("\n")) if not paragraph.lstrip().startswith("- ") else paragraph)
    result = "\n\n".join(kept)
    filled = common_words(context)
    filled.update(words or {})
    for name, value in filled.items():
        result = result.replace("{%s}" % name, value)
    put = getattr(context.walk, "put", None)
    # A copy of a conversation is told to answer nobody, so no question is put to it.
    for name in asked:
        resolved, unread = cache[name]
        if unread:
            result += "\n\nWhat was chosen for the setting `%s` on this machine cannot be read, so the text above is the one for `%s`: %s" % (
                name, resolved.effect, unread)
        elif resolved.asked() and not context.environ.get(asides.TOKEN) and (put is None or name not in put):
            result += "\n\n" + "\n".join(["Not settled on this machine yet. " + settings.menu(context, resolved)[0]] + settings.menu(context, resolved)[1:])
            if put is not None:
                put.append(name)
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
