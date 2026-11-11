"""The `jotting` setting: who notes the owner's corrections while a task is worked on.

Each answer asks more of the harness than the one before it, and falls back to that one where the
harness cannot do it: `aside` to `later`, `later` to `here`.
"""
from __future__ import annotations

import sys

from model.abstractions import Setting
from session import harness, history, settings

ID = "jotting"
HERE, LATER, ASIDE = "here", "later", "aside"
CAPTURE = "conversation"


class JottingSetting(Setting):
    id = ID
    asks = "Who notes the owner's corrections while a task is worked on?"
    options = (
        (HERE, "the working agent notes each one as it comes. Works in every harness; each note takes a moment of the work."),
        (LATER, "nobody during the work. What the owner said is read back from the conversation when the task is reviewed; a task that is never reviewed is read back by `/vesta-backfill`."),
        (ASIDE, "a copy of the conversation is started each time the owner says something; it notes a correction where there is one, and ends. The work is not interrupted. Each copy costs about what one reply costs."),
    )
    default = HERE
    put = True

    def effect(self, context, value):
        found = harness.current(context)
        name = found.name if found is not None else "this harness"
        if value == HERE:
            return HERE, ""
        if found is None or not found.history:
            return HERE, "the engine cannot read the conversations of %s" % name
        if not found.conversation():
            return HERE, "%s did not say which conversation this command was started from" % name
        missing = history.unfound(context, found.history, found.conversation())
        if missing:
            return HERE, "the engine does not find this conversation where %s keeps them (%s)" % (name, missing)
        if value == ASIDE and not found.forks:
            return LATER, "%s cannot start a copy of a conversation" % name
        return value, ""

    def turns_on(self, value):
        return {"capture": [CAPTURE]} if value in (LATER, ASIDE) else {}

    def after(self, context, value):
        effect = self.effect(context, value)[0]
        lines = [{
            HERE: "From now on in this task: at the moment the owner corrects or redirects the work, run `jot --steer -` with their words.",
            LATER: "From now on in this task: note no correction of the owner's as it comes; what the owner says is read back from the "
                   "conversation when the task is reviewed. A correction already noted stays.",
            ASIDE: "From now on in this task: note no correction of the owner's as it comes; a copy of the conversation notes it. "
                   "A correction already noted stays.",
        }[effect]]
        found = harness.current(context)
        if value != ASIDE or found is None or not found.forks:
            return lines
        command = '"%s" "%s/vesta/.engine" aside' % (sys.executable.replace("\\", "/"), context.root.replace("\\", "/"))
        path, entry = found.hook(command)
        return lines + [
            "",
            "One thing is left for the owner to do: %s starts the copy only where it is told to. Add this to `%s` in the project, "
            "merging it with what the file already holds. The file is this person's own: where the project is under version control, "
            "see that it is not committed." % (found.name, path),
            "",
        ] + entry.split("\n") + [
            "",
            "Until it is there, nothing is noted aside, and what the owner said is read back when the task is reviewed, as with `later`.",
        ]


def in_effect(context):
    return settings.in_effect(context, ID) if ID in settings.names(context) else HERE


MEMBER = JottingSetting
