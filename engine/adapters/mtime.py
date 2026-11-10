"""The `mtime` change source: a file counts as changed where its modification time is later than the base."""
from __future__ import annotations

import time

from kernel import root as roots
from kernel import tree as trees
from model.abstractions import ChangeSource

ENGINE_FOLDERS = tuple(trees.HOME + name + "/" for name in roots.ENGINES) + (trees.STATE,)


class MtimeSource(ChangeSource):
    """Reads modification times. It needs nothing but the files."""

    id = "mtime"
    residue = "a deleted file; a file changed and then given an older time; a file reached only through a linked folder"

    def mark(self):
        return {"source": self.id, "at": time.time_ns()}

    def changed_since(self, base):
        at = base.get("at", 0)
        found = []
        self._walk("", at if isinstance(at, int) else 0, found)
        return sorted(found)

    def _walk(self, folder, at, found):
        for name in self.tree.list(folder):
            path = (folder + "/" + name) if folder else name
            if self.tree.is_dir(path):
                if name in self.ignore or (path + "/").startswith(ENGINE_FOLDERS) or self.tree.is_link(path):
                    continue
                self._walk(path, at, found)
            else:
                changed = self.tree.changed_at(path)
                if changed is not None and changed > at:
                    found.append(path)


MEMBER = MtimeSource
