"""The release check: a release tag is `v` followed by the engine's version, and the copy of the
engine inside the vesta-init skill is the engine that was built.

Usage: python3 tools/release.py [--tag <tag>]

Prints the tag the engine's version calls for. With `--tag`, exits 1 where the tag given is not it.
Exits 1 where the skill's copy of the engine carries another version: run tools/build.py first.
"""
from __future__ import annotations

import os
import re
import sys

VERSION = re.compile(r'^ENGINE = "([0-9]+\.[0-9]+\.[0-9]+)"', re.M)
PLACES = ("engine/kernel/version.py", "skills/vesta-init/engine/kernel/version.py")


def version(root, place):
    with open(os.path.join(root, *place.split("/")), encoding="utf-8") as handle:
        found = VERSION.search(handle.read())
    if not found:
        raise ValueError("%s names no version" % place)
    return found.group(1)


def main(argv, root=None):
    root = root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    args = list(argv)
    tag = None
    if args[:1] == ["--tag"] and len(args) == 2:
        tag = args[1]
    elif args:
        sys.stderr.write(__doc__)
        return 2
    try:
        engine, copy = (version(root, place) for place in PLACES)
    except (OSError, ValueError) as error:
        sys.stderr.write("release: %s\n" % error)
        return 1
    if engine != copy:
        sys.stderr.write("release: engine/ is at %s and the copy in the vesta-init skill at %s; run tools/build.py.\n" % (engine, copy))
        return 1
    wanted = "v" + engine
    if tag is not None and tag != wanted:
        sys.stderr.write("release: the tag is %s and the engine is at %s; the tag for it is %s.\n" % (tag, engine, wanted))
        return 1
    print(wanted)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
