"""Row match: a row with `fires-on` globs fires where a glob matches one of the given paths."""
from __future__ import annotations

from kernel import glob
from stores import walks

FIRED, JUDGE = "fired", "judge"


def state(row, paths):
    """`fired` where one of the row's globs matches one of the paths; `judge` where the agent decides."""
    globs = walks.globs_of(row.get("fires-on", walks.JUDGED)) or []
    if any(glob.match(pattern, path) for pattern in globs for path in paths):
        return FIRED
    return JUDGE
