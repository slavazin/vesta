"""Entry point: python3 <this folder> <command>."""
import os
import sys

if sys.version_info < (3, 9):
    sys.stderr.write("vesta: this needs Python 3.9 or later; this is Python %d.%d.\n" % sys.version_info[:2])
    sys.exit(2)

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8", errors="strict")

try:
    from cli.main import main  # noqa: E402
except Exception as error:  # a file missing or cut short shows as an error while the engine loads
    sys.stderr.write(
        "vesta: this copy of the engine is not whole (%s: %s). Remove it and copy the `engine/` folder of the vesta-init "
        "skill there again; `/vesta-init upgrade` does that for the engine in place. Nothing was changed.\n" % (type(error).__name__, error)
    )
    sys.exit(2)

sys.exit(main(sys.argv[1:]))
