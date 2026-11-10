"""The `git` change source: what git reports as changed since the base, less what was already
changed when the base was taken and has not changed again."""
from __future__ import annotations

import os
import subprocess

from model.abstractions import ChangeSource, SourceError

PROGRAM = "git"
TIMEOUT = 30


def _git(root, *arguments, **options):
    """The output of one git command run at the root. Raises SourceError where it does not run."""
    command = [PROGRAM, "-C", root, "-c", "core.quotepath=off"] + list(arguments)
    try:
        done = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=TIMEOUT)
    except FileNotFoundError:
        raise SourceError("no `%s` program was found" % PROGRAM)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise SourceError("`%s %s` did not run (%s)" % (PROGRAM, arguments[0], error))
    if done.returncode and not options.get("lenient"):
        words = done.stderr.decode("utf-8", "replace").strip().split("\n")[0]
        raise SourceError("`%s %s` failed: %s" % (PROGRAM, arguments[0], words))
    return done.stdout.decode("utf-8", "replace") if not done.returncode else ""


def _names(text):
    return [name for name in text.split("\0") if name]


def _in_repository(root):
    here = os.path.abspath(root)
    while True:
        if os.path.exists(os.path.join(here, ".git")):
            return True
        parent = os.path.dirname(here)
        if parent == here:
            return False
        here = parent


class GitSource(ChangeSource):
    """Asks git. It is the only thing in the engine that runs a program."""

    id = "git"
    residue = "a file git ignores; a change that was committed and then undone by a further commit"

    @classmethod
    def usable(cls, root):
        if not _in_repository(root):
            return False, "the project is not inside a git repository"
        try:
            _git(root, "rev-parse", "--is-inside-work-tree")
        except SourceError as error:
            return False, "the project is inside a git repository and %s" % error
        return True, ""

    def _head(self):
        return _git(self.root, "rev-parse", "--verify", "--quiet", "HEAD", lenient=True).strip()

    def _stamp(self, path):
        changed = self.tree.changed_at(path)
        return 0 if changed is None else changed

    def _skipped(self, path):
        return any(part in self.ignore for part in path.split("/")[:-1])

    def mark(self):
        head = self._head()
        return {"source": self.id, "head": head, "dirty": dict((name, self._stamp(name)) for name in self._differing(head))}

    def _differing(self, head):
        """Every path that differs from a commit, staged or not, and every untracked path."""
        if head:
            names = set(_names(_git(self.root, "diff", "--name-only", "-z", "--relative", head)))
        else:
            names = set(_names(_git(self.root, "ls-files", "-z", "--cached")))
        names.update(_names(_git(self.root, "ls-files", "-z", "--others", "--exclude-standard")))
        return names

    def changed_since(self, base):
        head = base.get("head", "")
        dirty = base.get("dirty", {})
        names = self._differing(head)
        names.update(dirty)
        found = []
        for name in names:
            if self._skipped(name):
                continue
            if name in dirty and self._stamp(name) == dirty[name]:
                continue
            found.append(name)
        return sorted(found)


MEMBER = GitSource
