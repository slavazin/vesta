"""The `harness` setting: which program the agent runs in. Found from the environment the command
was started in; chosen where the owner wants nothing assumed, or where the engine finds the wrong one."""
from __future__ import annotations

from model.abstractions import Setting
from session import settings

TABLE = "harnesses"
ID = "harness"


def _members(context):
    return [(name, context.member(TABLE, name)) for name in context.known.get(TABLE, ())]


class HarnessSetting(Setting):
    id = ID
    asks = "Which program does the agent run in?"

    def __init__(self, context):
        self.context = context
        members = _members(context)
        self.options = tuple((name, "%s. What the engine cannot do in it: %s." % (cls.name, cls.residue)) for name, cls in members)
        # What is left where none is found: the one that assumes nothing.
        self.default = ([name for name, cls in members if not cls.known] or [""])[0]

    def found(self, context):
        for name, cls in _members(context):
            if cls.known and cls(context.environ).here():
                return name
        return ""


def current(context):
    """The harness in effect for this command, or None where the engine has none."""
    name = settings.in_effect(context, ID) if ID in settings.names(context) else ""
    return context.member(TABLE, name)(context.environ) if name in context.known.get(TABLE, ()) else None


MEMBER = HarnessSetting
