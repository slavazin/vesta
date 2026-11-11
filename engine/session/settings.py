"""Settings: what differs by the person or the machine and never by the project.

The project's own choices are in `vesta/vesta.yml` and are changed through a proposal. These are kept
under `vesta/.state/`, on this machine, and are chosen with the `setting` command. A sheet prints only
the text of the answer in effect, so what the other answers would have asked is never read.
"""
from __future__ import annotations

import json

from kernel.errors import UsageError

TABLE = "settings"
PATH = "vesta/.state/settings.json"
LOCK = "vesta/.state/settings.lock"
RULE = "vesta/INTERNALS.md, Settings"
CHOSEN, FOUND, DEFAULT = "chosen", "found", "default"


def names(context):
    return list(context.known.get(TABLE, ()))


def member(context, name):
    """The setting of that id. Raises UsageError where the engine has none."""
    if name not in names(context):
        raise UsageError("`%s` is not a setting; the settings are: %s" % (name, ", ".join(names(context)) or "none"))
    return context.member(TABLE, name)(context)


def read(tree):
    """What was chosen on this machine: {setting: answer}. Raises UsageError where the file does not read."""
    if not tree.is_file(PATH):
        return {}
    try:
        data = json.loads(tree.read(PATH))
    except (ValueError, UnicodeDecodeError, RecursionError):
        data = None
    if not isinstance(data, dict) or not all(isinstance(key, str) and isinstance(value, str) for key, value in data.items()):
        raise UsageError(
            "%s does not read. It holds what was chosen on this machine and no record, so this one file may be deleted by hand; "
            "every setting then goes back to what the engine finds. Then run the command again." % PATH
        )
    return data


def _change(context, change):
    with context.tree.lock(LOCK) as held:
        if not held:
            raise UsageError("another command is changing the settings at this moment; nothing was changed. Run this command again.")
        chosen = read(context.tree)
        change(chosen)
        context.tree.write(PATH, json.dumps(chosen, indent=1, sort_keys=True) + "\n")


def choose(context, name, value):
    """Keep an answer. Raises UsageError where it is no answer of that setting."""
    setting = member(context, name)
    values = [option for option, _ in setting.options]
    if value not in values:
        raise UsageError("`%s` is not an answer of `%s`; its answers are: %s" % (value, name, ", ".join(values)))
    _change(context, lambda chosen: chosen.__setitem__(name, value))


def clear(context, name):
    """Forget what was chosen. Returns whether anything was."""
    member(context, name)
    had = name in read(context.tree)
    if had:
        _change(context, lambda chosen: chosen.pop(name, None))
    return had


class Resolved(object):
    """A setting as it stands: `value` is the answer chosen, found or fallen back to, and `how` which
    of those; `effect` is the answer that takes effect here and `why` says why it is another; `stale`
    is an answer that was chosen and is none of the setting's."""

    def __init__(self, setting, value, how, effect, why, stale=""):
        self.setting, self.value, self.how, self.effect, self.why, self.stale = setting, value, how, effect, why, stale

    @property
    def open(self):
        """The answers that would take effect here as themselves."""
        return self._open

    def asked(self):
        """Say whether the question is still to be put to the owner."""
        return self.setting.put and self.how != CHOSEN and len(self._open) > 1


def resolve(context, name, kept=None):
    """A setting as it stands. `kept` stands in for what was chosen, where the caller has read it or could not."""
    setting = member(context, name)
    values = [option for option, _ in setting.options]
    chosen = (read(context.tree) if kept is None else kept).get(name)
    stale = chosen if chosen is not None and chosen not in values else ""
    if chosen in values:
        value, how = chosen, CHOSEN
    else:
        found = setting.found(context)
        value, how = (found, FOUND) if found in values else (setting.default, DEFAULT)
    effect, why = setting.effect(context, value)
    resolved = Resolved(setting, value, how, effect, why, stale)
    resolved._open = [option for option in values if setting.effect(context, option)[0] == option]
    return resolved


def in_effect(context, name):
    """The answer of a setting that takes effect here. Where what was chosen cannot be read, the
    answer is the one that holds with nothing chosen: work goes on, and `setting`, `doctor` and the
    sheet that depends on the setting name the file."""
    try:
        return resolve(context, name).effect
    except UsageError:
        return resolve(context, name, {}).effect


def turned_on(context, table):
    """The members the settings in effect add to a table for this person, in the settings' order."""
    found = []
    for name in names(context):
        try:
            resolved = resolve(context, name)
        except UsageError:
            resolved = resolve(context, name, {})
        found.extend(resolved.setting.turns_on(resolved.effect).get(table, ()))
    return list(dict.fromkeys(found))


def fallen(context, table):
    """[(setting, the answer chosen or found, why it is not in effect)] for each setting whose answer
    would have added a member to a table and, falling back, does not."""
    found = []
    for name in names(context):
        try:
            resolved = resolve(context, name)
        except UsageError:
            continue
        if resolved.setting.turns_on(resolved.value).get(table) and not resolved.setting.turns_on(resolved.effect).get(table):
            found.append((name, resolved.value, resolved.why))
    return found


def said(resolved):
    """A setting in one sentence: its answer, how it came, and what is in effect where that differs."""
    how = {CHOSEN: "chosen", FOUND: "found by the engine", DEFAULT: "not chosen: the answer until one is"}[resolved.how]
    line = "`%s` (%s)" % (resolved.value, how)
    if resolved.effect != resolved.value:
        line += "; in effect: `%s`, because %s" % (resolved.effect, resolved.why)
    if resolved.stale:
        line += "; `%s` was chosen before and is no answer of it, so it counts for nothing" % " ".join(resolved.stale.split())[:40]
    return line


def menu(context, resolved, command=""):
    """The question of a setting with one line for each answer that can take effect here."""
    setting = resolved.setting
    lines = ["%s Ask the owner once, and keep the answer with `%ssetting %s <answer>`:" % (setting.asks, command, setting.id)]
    lines.extend("- `%s`: %s" % (value, line) for value, line in setting.options if value in resolved.open)
    lines.append("Until one is chosen, `%s` is in effect." % resolved.effect)
    return lines
