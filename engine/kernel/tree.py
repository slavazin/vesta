"""The Tree: every file the engine reads or writes goes through one.

Paths are relative to the project root and use `/`. The disk tree reads the project and writes only
under `vesta/`. An overlay holds pending writes and moves in memory; reads through it see the project as
it would be, and `commit` puts the changes on disk under a journal, so they land wholly or not at all.
"""
from __future__ import annotations

import contextlib
import json
import os
import threading
import time

from kernel.errors import Refusal, UsageError

HOME = "vesta/"
STATE = "vesta/.state/"
JOURNAL = "vesta/.state/journal.json"
COMMIT_LOCK = "vesta/.state/commit.lock"
# Held by a command that decides from what it read: no other such command reads or writes meanwhile.
COMMAND_LOCK = "vesta/.state/command.lock"
# A lock is tried for about two seconds; one older than ten is taken to be left by a command that died.
# A lock is waited for by the clock, for four seconds: well under the ten after which one is taken for
# abandoned, however slowly the machine sleeps between tries.
LOCK_PATIENCE, LOCK_WAIT, LOCK_STALE = 4.0, 0.02, 10


def clean(path):
    """A path in the tree's form. Raises ValueError for one that is absolute or leaves the root."""
    path = path.replace("\\", "/")
    if path.startswith("/") or (len(path) > 1 and path[1] == ":"):
        raise ValueError("a path is relative to the project root: %r" % (path,))
    parts = []
    for part in path.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            raise ValueError("a path may not leave the project root: %r" % (path,))
        parts.append(part)
    return "/".join(parts)


def inside_home(path):
    """A cleaned path, refused where it is not under `vesta/`."""
    path = clean(path)
    if not path.startswith(HOME):
        raise ValueError("the engine writes only under %s: %r" % (HOME, path))
    return path


def as_text(text):
    """A text as it goes to disk: LF line endings, and refused where it does not encode as UTF-8."""
    text = text.replace("\r\n", "\n")
    text.encode("utf-8")
    return text


class Tree(object):
    """The file interface. `DiskTree` and `Overlay` implement it."""

    def exists(self, path):
        return self.is_file(path) or self.is_dir(path)

    def keep(self, *paths):
        """Mark locks as still held; a tree with no locks has nothing to do."""

    def is_file(self, path):
        raise NotImplementedError

    def is_dir(self, path):
        raise NotImplementedError

    def read(self, path):
        """The text of a file, CRLF read as LF. Raises FileNotFoundError."""
        raise NotImplementedError

    def list(self, path):
        """The sorted names in a folder; empty where it is not a folder."""
        raise NotImplementedError

    def write(self, path, text):
        raise NotImplementedError

    def move(self, source, target):
        """Move a file. Refuses where the target exists: a record is never written over by a move."""
        raise NotImplementedError

    def remove(self, path):
        """Delete a file of the working state under `vesta/.state/`. Nothing else is deleted."""
        raise NotImplementedError

    def size(self, path):
        """The size of a file in bytes, or None where it is not a file."""
        raise NotImplementedError

    def changed_at(self, path):
        """When a file was last changed, in nanoseconds; None where it is not there."""
        raise NotImplementedError

    def leaves_root(self, path):
        """Say whether a path, followed through any link, ends outside the project root."""
        return False

    def is_link(self, path):
        """Say whether a path is itself a link to another place."""
        return False

    @contextlib.contextmanager
    def lock(self, path):
        """Hold a path as a lock while the block runs, so that two commands do not both read a file,
        change it and write it back. Yields whether the lock was taken. A tree with nothing to
        guard holds nothing."""
        yield True

    def read_or(self, path, default=""):
        return self.read(path) if self.is_file(path) else default

    def append(self, path, text):
        """Add text to the end of a file, creating it where absent."""
        self.write(path, self.read_or(path) + text)

    def walk(self, path):
        """Every file under a folder, as sorted tree paths."""
        found = []
        for name in self.list(path):
            child = (path + "/" + name) if path else name
            if self.is_dir(child):
                found.extend(self.walk(child))
            else:
                found.append(child)
        return found


def in_state(path):
    path = clean(path)
    if not path.startswith(STATE):
        raise ValueError("the engine deletes only under %s: %r" % (STATE, path))
    return path


class DiskTree(Tree):
    """The project on disk."""

    RETRIES = 5
    HELD = 2.0  # seconds to wait for a file another command holds open, where the system refuses meanwhile
    TEMPORARY = ".tmp-"

    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.written = []

    def size(self, path):
        full = self.locate(path)
        return os.path.getsize(full) if os.path.isfile(full) else None

    def changed_at(self, path):
        try:
            return os.stat(self.locate(path)).st_mtime_ns
        except OSError:
            return None

    def is_link(self, path):
        return os.path.islink(self.locate(path))

    @contextlib.contextmanager
    def lock(self, path):
        full = self.locate(path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        held = False
        until = time.monotonic() + LOCK_PATIENCE
        while True:
            try:
                os.close(os.open(full, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
                held = True
                break
            except (FileExistsError, PermissionError):
                # Held by another command; on Windows a lock being removed refuses the attempt the same way.
                try:
                    if time.time() - os.path.getmtime(full) > LOCK_STALE:
                        os.unlink(full)
                        continue
                except OSError:
                    pass
                if time.monotonic() >= until:
                    break
                time.sleep(LOCK_WAIT)
        try:
            yield held
        finally:
            if held:
                try:
                    os.unlink(full)
                except OSError:
                    pass

    def keep(self, *paths):
        """Mark each lock that exists as still held, so a long change is not taken for a stopped one."""
        for path in paths:
            try:
                os.utime(self.locate(path), None)
            except OSError:
                pass

    def leaves_root(self, path):
        root = os.path.realpath(self.root)
        try:
            return os.path.commonpath([root, os.path.realpath(self.locate(path))]) != root
        except ValueError:
            return True

    def locate(self, path):
        """The absolute path of a tree path."""
        path = clean(path)
        return os.path.join(self.root, *path.split("/")) if path else self.root

    def is_file(self, path):
        return os.path.isfile(self.locate(path))

    def is_dir(self, path):
        return os.path.isdir(self.locate(path))

    def read(self, path):
        text = self._patiently(self._bytes, self.locate(path)).decode("utf-8")
        if text.startswith("\ufeff"):
            text = text[1:]
        return text.replace("\r\n", "\n")

    def list(self, path):
        full = self.locate(path)
        if not os.path.isdir(full):
            return []
        return sorted(name for name in os.listdir(full) if self.TEMPORARY not in name)

    def _target(self, path):
        """The absolute path for a write, refused where it is not really inside `vesta/`: a link
        that leads out of the folder does not make its target writable."""
        full = self.locate(inside_home(path))
        home = os.path.realpath(os.path.join(self.root, HOME.strip("/")))
        folder = os.path.realpath(os.path.dirname(full))
        if os.path.commonpath([home, folder]) != home or os.path.islink(full):
            raise ValueError("the engine writes only under %s, and %r leads outside it" % (HOME, path))
        return full

    @staticmethod
    def _bytes(full):
        with open(full, "rb") as handle:
            return handle.read()

    def _patiently(self, act, *arguments):
        """Do one file operation, trying again while Windows refuses it because another command has
        the file open for a moment. Elsewhere a refusal is not passing, and a few tries are enough."""
        until = time.monotonic() + (self.HELD if os.name == "nt" else self.RETRIES * LOCK_WAIT)
        while True:
            try:
                return act(*arguments)
            except PermissionError:
                if time.monotonic() >= until:
                    raise
                time.sleep(LOCK_WAIT)

    def _replace(self, source, full):
        try:
            self._patiently(os.replace, source, full)
        except PermissionError:
            raise OSError("could not write %s: permission was refused, or another program holds the file open" % full)

    def write(self, path, text):
        full = self._target(path)
        data = as_text(text).encode("utf-8")
        os.makedirs(os.path.dirname(full), exist_ok=True)
        # Named for this process and thread, so that two writers of one file never share a temporary file.
        temporary = "%s%s%d-%d" % (full, self.TEMPORARY, os.getpid(), threading.get_ident())
        try:
            with open(temporary, "wb") as handle:
                handle.write(data)
            self._replace(temporary, full)
            self.written.append(clean(path))
        finally:
            if os.path.isfile(temporary):
                os.remove(temporary)

    def move(self, source, target):
        source_full, target_full = self._target(source), self._target(target)
        if os.path.exists(target_full):
            raise ValueError("%r is already there; a move does not write over a file" % (clean(target),))
        os.makedirs(os.path.dirname(target_full), exist_ok=True)
        self._replace(source_full, target_full)
        self.written.extend([clean(source), clean(target)])

    def make_dir(self, path):
        """Create an empty folder under `vesta/`."""
        full = self._target(path + "/x")
        os.makedirs(os.path.dirname(full), exist_ok=True)

    def remove(self, path):
        full = self.locate(in_state(path))
        if os.path.isfile(full):
            os.remove(full)

    def unlink(self, path):
        """Remove the source of a committed move, or a file an unfinished commit left. Only the
        overlay's commit and the recovery call this."""
        full = self._target(path)
        if os.path.isfile(full):
            os.remove(full)
            self.written.append(clean(path))

    def sweep(self, path):
        """Remove temporary files an interrupted write left beside a path."""
        folder, name = os.path.split(self.locate(inside_home(path)))
        if os.path.isdir(folder):
            for leaf in os.listdir(folder):
                if leaf.startswith(name + self.TEMPORARY):
                    os.remove(os.path.join(folder, leaf))


class Overlay(Tree):
    """Pending writes and moves over a base tree. Every path is checked when it is given, so a
    commit meets no refusal half way."""

    def __init__(self, base):
        self.base = base
        self.writes = {}
        self.gone = set()

    def is_file(self, path):
        path = clean(path)
        if path in self.writes:
            return True
        return path not in self.gone and self.base.is_file(path)

    def is_dir(self, path):
        path = clean(path)
        prefix = path + "/" if path else ""
        if any(name.startswith(prefix) for name in self.writes):
            return True
        return self.base.is_dir(path)

    def read(self, path):
        path = clean(path)
        if path in self.writes:
            return self.writes[path]
        if path in self.gone:
            raise FileNotFoundError(path)
        return self.base.read(path)

    def size(self, path):
        path = clean(path)
        if path in self.writes:
            return len(self.writes[path].encode("utf-8"))
        return None if path in self.gone else self.base.size(path)

    def changed_at(self, path):
        return self.base.changed_at(path)

    def leaves_root(self, path):
        return self.base.leaves_root(path)

    def is_link(self, path):
        return self.base.is_link(path)

    def list(self, path):
        path = clean(path)
        prefix = path + "/" if path else ""
        names = set(name for name in self.base.list(path) if prefix + name not in self.gone)
        for name in self.writes:
            if name.startswith(prefix):
                names.add(name[len(prefix):].split("/", 1)[0])
        return sorted(names)

    def _free(self, path):
        """Refuse a path that would sit under a file, or on a folder."""
        parts = path.split("/")
        for count in range(1, len(parts)):
            if self.is_file("/".join(parts[:count])):
                raise ValueError("%r lies under a file" % (path,))
        if self.is_dir(path):
            raise ValueError("%r is a folder" % (path,))

    def write(self, path, text):
        path = inside_home(path)
        self._free(path)
        if self.base.leaves_root(path):
            raise Refusal("%s is a link that leads outside the project, and the engine writes only inside it. Replace the link with the file itself. Nothing was changed." % path, "vesta/INTERNALS.md, How changes are made")
        self.writes[path] = as_text(text)
        self.gone.discard(path)

    def move(self, source, target):
        source, target = inside_home(source), inside_home(target)
        if self.is_file(target):
            raise ValueError("%r is already there; a move does not write over a file" % (target,))
        text = self.read(source)
        self.writes.pop(source, None)
        if self.base.is_file(source):
            self.gone.add(source)
        self.write(target, text)

    def remove(self, path):
        path = in_state(path)
        self.writes.pop(path, None)
        if self.base.is_file(path):
            self.gone.add(path)

    def changed(self):
        """Every path a commit would write or remove, sorted."""
        return sorted(set(self.writes) | self.gone)

    def commit(self):
        """Put the pending changes on disk under the journal, then clear them. Returns the paths."""
        paths = self.changed()
        if not paths:
            return []
        with self.base.lock(COMMIT_LOCK) as held:
            if not held:
                raise UsageError("another command is writing under vesta/ at this moment; nothing was written. Run the command again.")
            return self._commit(paths)

    def _commit(self, paths):
        before = dict((path, self.base.read(path) if self.base.is_file(path) else None) for path in paths)
        self.base.write(JOURNAL, json.dumps({"paths": before}, indent=1, sort_keys=True) + "\n")
        for path in sorted(self.writes):
            self.base.write(path, self.writes[path])
            self.base.keep(COMMIT_LOCK, COMMAND_LOCK)
        for path in sorted(self.gone):
            self.base.unlink(path)
        self.base.remove(JOURNAL)
        self.writes = {}
        self.gone = set()
        return paths


def recover(disk):
    """Undo a commit that did not finish. Returns the paths restored; empty where no journal is found.

    A path that cannot be put back is left, and named in the UsageError raised once the rest is done.
    """
    if not disk.is_file(JOURNAL):
        return []
    with disk.lock(COMMIT_LOCK) as held:
        if held:
            return _recover(disk) if disk.is_file(JOURNAL) else []
        if disk.is_file(JOURNAL):
            # Another command is part-way through a change, or stopped part-way a moment ago: what is on disk is half of it.
            raise UsageError("a change to several files under vesta/ is part-way through. Nothing was read or changed; run this command again in a few seconds.")
        return []


def _recover(disk):
    try:
        before = json.loads(disk.read(JOURNAL))["paths"]
    except (ValueError, KeyError, TypeError):
        raise UsageError(
            "%s does not read, so an unfinished change cannot be undone. Look at the files under vesta/ "
            "that changed last, then delete that file." % JOURNAL
        )
    restored, stuck = [], []
    for path in sorted(before):
        content = before[path]
        try:
            disk.sweep(path)
            if content is None:
                if disk.is_file(path):
                    disk.unlink(path)
                    restored.append(path)
            elif not disk.is_file(path) or disk.read(path) != content:
                disk.write(path, content)
                restored.append(path)
        except (ValueError, OSError) as error:
            stuck.append("%s (%s)" % (path, error))
    if stuck:
        raise UsageError(
            "an unfinished change could not be undone for: %s. Fix what blocks each path and run the command again."
            % "; ".join(stuck)
        )
    disk.remove(JOURNAL)
    return restored
