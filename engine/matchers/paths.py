"""What every probe does with a path before it reads anything: keep it inside the project."""
from __future__ import annotations

from kernel import tree as trees
from model.abstractions import MatchError


def inside(text):
    """A probe's path in the tree's form. Raises MatchError for one that names a place outside the project."""
    try:
        path = trees.clean(text.strip())
    except ValueError:
        raise MatchError("`%s` leaves the project; a probe reads only inside it" % text.strip())
    if not path:
        raise MatchError("the probe names no path")
    return path


def guarded(tree, path):
    """The path, refused where a link takes it outside the project."""
    if tree.leaves_root(path):
        raise MatchError("`%s` leads outside the project through a link; a probe reads only inside it" % path)
    return path
