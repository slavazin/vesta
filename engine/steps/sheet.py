"""The sheet printer: the steps of a checkpoint, in the order the configuration gives, printed in parts.

A part runs from its first step up to, and not including, the next step whose data exists only after
the earlier steps have been carried out. It ends with the command that prints the next part, or by
saying the walk is complete.
"""
from __future__ import annotations

from kernel.errors import UsageError
from stores import walks
from steps import instruction
from steps.base import NONE

TABLE = "steps"


class Walk(object):
    """One run of a checkpoint's walk: what the command line gave, and the session it runs in.
    `paths` are the ones the command line gave; `matched` the ones the mechanical matches run against."""

    def __init__(self, checkpoint, session, paths=(), ask="", requested=(), short=False):
        self.checkpoint = checkpoint
        self.session = session
        self.paths = list(paths)
        self.matched = list(paths)
        self.ask = ask
        self.requested = tuple(requested)
        self.short = short
        self.file = None
        self.said = []
        # The settings whose question this printing has already put to the owner.
        self.put = []


def _title(context, walk):
    title = walk.file.document.title if walk.file is not None else ""
    return title or ("Walk: %s" % walk.checkpoint.id)


def steps_of(context, walk):
    """([the steps that have a section in this walk, in order], [configured ids this engine lacks])."""
    wanted = walk.checkpoint.short if walk.short else walk.checkpoint.steps
    present, lacking = [], []
    for name in dict.fromkeys(wanted):
        if name not in context.known.get(TABLE, ()):
            lacking.append(name)
            continue
        step = context.member(TABLE, name)()
        if step.on_request and name not in walk.requested:
            continue
        if not context.config.level_reached(step.lowest_level):
            continue
        if step.present(context):
            present.append(step)
    return present, lacking


def part(steps, start):
    """The steps of one part, and the step the next part starts at (None where there is none)."""
    first = 0
    if start is not None:
        names = [step.id for step in steps]
        if start not in names:
            raise UsageError("`--from %s` names no step of this walk; its steps are: %s" % (start, ", ".join(names) or "none"))
        first = names.index(start)
    last = first + 1
    while last < len(steps) and not (steps[last].live and not (steps[last].joins and steps[last - 1].live)):
        last += 1
    return steps[first:last], (steps[last] if last < len(steps) else None)


def following(context, walk):
    """The step the second part of a walk starts at, or None where it has one part."""
    walk.file = walks.read(context.tree, walk.checkpoint.walk)
    context.walk = walk
    steps, _ = steps_of(context, walk)
    return part(steps, None)[1]


def command_line(context):
    return 'python3 "%s/vesta/.engine"' % context.root.replace("\\", "/")


def render(context, walk, start=None):
    """The lines of one part of the sheet."""
    walk.file = walks.read(context.tree, walk.checkpoint.walk)
    context.walk = walk
    context.session = walk.session
    if walk.short and not walk.checkpoint.short:
        raise UsageError("the `%s` walk has no short form; `checkpoints.%s.short` in vesta/vesta.yml names none" % (walk.checkpoint.id, walk.checkpoint.id))
    steps, lacking = steps_of(context, walk)
    chosen, following = part(steps, start)
    numbers = dict((step.id, position + 1) for position, step in enumerate(steps))
    lines = ["# %s%s" % (_title(context, walk), " (short form)" if walk.short else ""), ""]
    lines.append(walk.session.heading)
    lines.extend(walk.said)
    if walk.session.asks:
        lines.append("%s: %s" % (walk.session.ask_word, walk.session.asks[-1]))
    if walk.paths:
        lines.append("Paths given: %s" % ", ".join("`%s`" % path for path in walk.paths))
    lines.append("")
    lines.append("Steps of this walk: %s" % (" · ".join("%d. %s" % (numbers[step.id], step.title) for step in steps) or NONE))
    if lacking:
        lines.append("Not printed, because this engine has no such step: %s. `check` says more." % ", ".join("`%s`" % name for name in lacking))
    lines.append("")
    lines.append("Carry out each section from top to bottom; its **Do** line is an instruction for now. Run each command named below as `%s <command>`." % command_line(context))
    for step in chosen:
        section = step.render(context)
        lines.extend(["", "## %d. %s" % (numbers[step.id], section.title), ""])
        lines.extend(section.data if section.data else [NONE])
        lines.extend(["", "**Do:** " + section.instruction])
    lines.extend(["", "---", ""])
    if following is not None:
        option = (" --short" if walk.short else "") + "".join(" --with %s" % name for name in walk.requested)
        lines.append(
            "This part ends here. Once every **Do** above is carried out, print the next part with `walk %s%s --from %s%s`."
            % (walk.checkpoint.id, option, following.id, walk.session.resume)
        )
    else:
        after = instruction.read("after-" + walk.checkpoint.id)
        if after is not None:
            lines.extend([instruction.fill(after, context), ""])
        lines.append("The walk is complete: no further part follows.")
    return lines
