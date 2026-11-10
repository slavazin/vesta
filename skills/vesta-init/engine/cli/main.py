"""Argument parsing and dispatch.

Exit codes: 0 the command ran; 1 only from `check`, on an error finding; 2 a usage or configuration
error; 3 refused, because the command would break a rule.
"""
from __future__ import annotations

import contextlib
import os
import sys

from cli import build, handedits, manifest, sessions, upgrading
from kernel import root as roots
from kernel import tree as trees
from kernel.errors import Refusal, SubsetError, UsageError
from model.abstractions import SourceError

OK, FOUND, USAGE, REFUSED = 0, 1, 2, 3


def usage():
    lines = ["usage: python3 <project>/vesta/.engine <command> [options]", "", "commands:"]
    for name in manifest.COMMANDS:
        lines.append("  %-8s %s" % (name, manifest.SUMMARIES.get(name, "")))
    lines.extend(["", "Free text given as `-` is read from standard input, so no shell quoting touches it."])
    return "\n".join(lines) + "\n"


@contextlib.contextmanager
def _alone(disk, wanted):
    """Hold the command lock for a command that builds a change from what it reads, so that two of
    them never build on the same state. Raises UsageError where another holds it."""
    if not wanted:
        yield
        return
    with disk.lock(trees.COMMAND_LOCK) as held:
        if not held:
            raise UsageError(
                "another command is changing vesta/ at this moment; nothing was changed. Run this command again. Where a command "
                "was stopped part-way, what it held is released %d seconds after it stopped." % trees.LOCK_STALE
            )
        yield


def _damaged():
    """Say whether this copy of the engine lacks or holds changed one of its own files."""
    try:
        return bool(build.shipped().whole())
    except Exception:
        return True


def main(argv, root=None, clock=None, out=None, err=None, stdin=None):
    """Run one command. `root`, `clock`, `out` and `err` are for callers inside one process."""
    out = out if out is not None else sys.stdout
    err = err if err is not None else sys.stderr
    if not argv:
        err.write(usage())
        return USAGE
    if argv[0] in ("-h", "--help", "help") or "--help" in argv[1:] or "-h" in argv[1:]:
        out.write(usage())
        return OK
    name, arguments = argv[0], list(argv[1:])
    if name not in manifest.COMMANDS:
        err.write("vesta: `%s` is not a command.\n%s" % (name, usage()))
        return USAGE
    if root is None:
        root = roots.from_engine(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if root is None:
        err.write("vesta: this engine is not inside a project's vesta/ folder; run it as `python3 <project>/vesta/.engine`.\n")
        return USAGE
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        module = manifest.command(name)
        restored = trees.recover(trees.DiskTree(root))
        if restored:
            out.write("An earlier command stopped before it finished. These files were put back as they were:\n")
            for path in restored:
                out.write("- %s\n" % path)
            out.write("\n")
        alone = getattr(module, "ALONE", False)
        if getattr(module, "BEFORE_SETUP", False):
            with _alone(trees.DiskTree(root), alone):
                return module.run_bare(root, arguments, out, clock)
        for line in upgrading.notes(trees.DiskTree(root), here):
            out.write(line + "\n")
        with _alone(trees.DiskTree(root), alone):
            context = build.context(root, out, clock)
            context.stdin = stdin
            for line in handedits.log(context, alone):
                out.write(line + "\n")
            code = module.run(context, arguments)
            sessions.note_written(context)
        return code
    except UsageError as error:
        err.write("vesta: %s\n" % error)
        return USAGE
    except Refusal as error:
        out.write("Refused: %s\n" % error.message)
        if error.rule:
            out.write("The rule is in %s.\n" % error.rule)
        return REFUSED
    except SubsetError as error:
        err.write("vesta: %s\n" % error)
        return USAGE
    except UnicodeDecodeError as error:
        err.write("vesta: a file the engine needs is not UTF-8 text (%s). Save it as UTF-8 and run the command again.\n" % error.reason)
        return USAGE
    except SourceError as error:
        err.write("vesta: %s. `doctor` shows how changed files are found.\n" % error)
        return USAGE
    except OSError as error:
        err.write("vesta: a file or folder could not be read or written (%s). Fix what blocks it and run the command again.\n" % error)
        return USAGE
    except Exception as error:  # the last line of defence: a command never ends in a traceback
        if isinstance(error, (ImportError, SyntaxError)) or _damaged():
            err.write(
                "vesta: this copy of the engine is not whole (%s: %s). Remove it and copy the `engine/` folder of the vesta-init "
                "skill there again; `/vesta-init upgrade` does that for the engine in place. Nothing was changed.\n" % (type(error).__name__, error)
            )
            return USAGE
        err.write(
            "vesta: the command stopped on an error it did not expect (%s: %s). If a change to several files was "
            "under way, the next command puts back the ones it had not finished.\n" % (type(error).__name__, error)
        )
        return USAGE
