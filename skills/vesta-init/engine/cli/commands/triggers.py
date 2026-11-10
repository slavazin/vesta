"""`triggers`: every live trigger of the recalled stores, with the state of its probe. It records nothing."""
from __future__ import annotations

from cli import args
from matchers import triggers
from steps.triggers import lines_of


def run(context, arguments):
    args.split(arguments)
    context.write("# Live triggers")
    context.write()
    for line in lines_of(triggers.live(context, context.stores.recalled())) or ["none"]:
        context.write(line)
    context.write()
    context.write("A probe is read from the project's files as they stand. A trigger with no probe is judged by reading its `if`.")
    return 0
