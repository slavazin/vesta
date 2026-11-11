"""The `review` setting: who carries out the part of the end-of-task review that only reads and writes notes.

The part that puts choices to the owner is always carried out in the working conversation.
"""
from __future__ import annotations

from model.abstractions import Setting
from session import harness, settings

ID = "review"
HERE, ASIDE = "here", "aside"


class ReviewSetting(Setting):
    id = ID
    asks = "Who carries out the first part of the end-of-task review, which reads the task back and writes notes?"
    options = (
        (HERE, "the working agent, in the working conversation. Works in every harness; the whole review sheet is read there."),
        (ASIDE, "a copy of the conversation, which carries the part out and ends. The working conversation reads only what the copy wrote, "
                "and goes on with the part that is put to the owner. The copy costs about what the part costs here."),
    )
    default = HERE

    def effect(self, context, value):
        found = harness.current(context)
        name = found.name if found is not None else "this harness"
        if value == ASIDE and not (found is not None and found.forks):
            return HERE, "%s cannot start a copy of a conversation" % name
        if value == ASIDE and not found.conversation():
            return HERE, "%s did not say which conversation this command was started from" % name
        return value, ""


def in_effect(context):
    return settings.in_effect(context, ID) if ID in settings.names(context) else HERE


MEMBER = ReviewSetting
