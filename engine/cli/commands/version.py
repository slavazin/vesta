"""`version`: the engine version and the folder's schema number."""
from __future__ import annotations

from cli import args
from kernel.version import ENGINE


def run(context, arguments):
    args.split(arguments)
    context.write("engine %s" % ENGINE)
    context.write("schema %d" % context.config.schema)
    return 0
