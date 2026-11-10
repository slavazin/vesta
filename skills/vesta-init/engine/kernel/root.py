"""The root finder. The project root is the folder that holds `vesta/`."""
from __future__ import annotations

import os
import shutil
import time

FOLDER = "vesta"
CONFIG = "vesta.yml"


ENGINES = (".engine", ".engine.next")


def from_engine(engine_dir):
    """The root for an engine at `<root>/vesta/.engine/` (or `.engine.next/`), or None where it sits elsewhere."""
    engine_dir = os.path.abspath(engine_dir)
    home = os.path.dirname(engine_dir)
    if os.path.basename(home) != FOLDER or os.path.basename(engine_dir) not in ENGINES:
        return None
    return os.path.dirname(home)


OLD = ENGINES[0] + ".old"
TRIES, WAIT = 5, 0.1


def _clear(path):
    """Remove whatever stands at a path: a folder, a file or a link."""
    if os.path.islink(path) or os.path.isfile(path):
        os.remove(path)
    elif os.path.isdir(path):
        shutil.rmtree(path)


def _rename(source, target):
    """Rename a folder, trying again where another program holds a file in it for a moment."""
    for attempt in range(TRIES):
        try:
            os.rename(source, target)
            return
        except OSError:
            if attempt == TRIES - 1:
                raise
            time.sleep(WAIT)


def swap(root):
    """Put the new engine in the place of the one that ran until now, and remove the old one.
    Where the new one cannot be put in place the old one is put back, and OSError is raised.
    It may be run again after a stop at any point: it goes on from what it finds."""
    home = os.path.join(root, FOLDER)
    current, new, old = (os.path.join(home, name) for name in (ENGINES[0], ENGINES[1], OLD))
    if not os.path.isdir(new):
        return
    if os.path.isdir(current) or os.path.islink(current):
        _clear(old)
        _rename(current, old)
    try:
        _rename(new, current)
    except OSError:
        if os.path.isdir(old) and not os.path.exists(current):
            os.rename(old, current)
        raise
    shutil.rmtree(old, ignore_errors=True)


def from_folder(start):
    """The nearest folder at or above `start` that holds `vesta/vesta.yml`, or None."""
    here = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(here, FOLDER, CONFIG)):
            return here
        parent = os.path.dirname(here)
        if parent == here:
            return None
        here = parent
