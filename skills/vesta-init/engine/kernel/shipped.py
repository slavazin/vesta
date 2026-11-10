"""The text the engine ships: the files under its own `templates/` folder.

`vesta/` holds what the engine scaffolds a project with; the files beside it are shipped text the
engine compares against. These are read from the engine's own location, never from the project.
"""
from __future__ import annotations

import hashlib
import os

import json

FOLDER = "templates"
PROJECT = "vesta"
LIST = "shipped.json"
# The list of the engine's own files, at the engine's top: what a copy must hold to be whole.
CODE = "files.json"
# Left out of that list: the shipped text (it has its own), the tests (a project's copy has none).
OUTSIDE = (FOLDER, "tests")
# In a project, the fingerprint of every scaffold file as shipped: what an upgrade compares against.
MANIFEST = "vesta/.manifest.json"


def listing(fingerprints):
    """The text of a fingerprint list."""
    return json.dumps(fingerprints, indent=1, sort_keys=True) + "\n"


def _walk(top):
    """Every file under a folder as a `/` path relative to it, less bytecode and desktop litter, sorted."""
    found = []
    for folder, names, leaves in os.walk(top):
        names[:] = sorted(name for name in names if name != "__pycache__")
        for leaf in leaves:
            if not leaf.endswith(".pyc") and leaf != ".DS_Store":
                found.append(os.path.relpath(os.path.join(folder, leaf), top).replace(os.sep, "/"))
    return sorted(found)


def digest(text):
    """The fingerprint of a text: the SHA-256 of its UTF-8 bytes with LF line endings."""
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


class Shipped(object):
    """The shipped text of one engine."""

    def __init__(self, engine_dir):
        self.base = os.path.join(os.path.abspath(engine_dir), FOLDER)

    def read(self, name):
        """A shipped file's text by its path under `templates/`, with `/` separators."""
        with open(os.path.join(self.base, *name.split("/")), "rb") as handle:
            return handle.read().decode("utf-8").replace("\r\n", "\n")

    def every(self):
        """The path of every shipped file under `templates/`, less the list itself, sorted."""
        return [name for name in _walk(self.base) if name != LIST]

    def fingerprints(self):
        """`{path: fingerprint}` of the shipped files as they stand in this copy."""
        return dict((name, digest(self.read(name))) for name in self.every())

    def damage(self):
        """What this copy of the engine lacks or holds changed, against the list the build wrote."""
        try:
            listed = json.loads(self.read(LIST))
            if not isinstance(listed, dict) or not listed:
                raise ValueError(LIST)
        except (OSError, ValueError, UnicodeDecodeError):
            return ["%s/%s is missing or does not read" % (FOLDER, LIST)]
        found = []
        for name in sorted(listed):
            try:
                if digest(self.read(name)) != listed[name]:
                    found.append("%s/%s is not the text that was shipped" % (FOLDER, name))
            except UnicodeDecodeError:
                found.append("%s/%s does not read as text" % (FOLDER, name))
            except OSError:
                found.append("%s/%s is missing" % (FOLDER, name))
        found.extend("%s/%s is not a file that was shipped" % (FOLDER, name) for name in self.every() if name not in listed)
        return found

    def project_files(self):
        """The path of every file of the scaffold, relative to the project's `vesta/` folder, sorted."""
        return _walk(os.path.join(self.base, PROJECT))

    def code(self):
        """`{path: fingerprint}` of the engine's own files as they stand in this copy, from its top."""
        top = os.path.dirname(self.base)
        found = {}
        for name in self._own():
            with open(os.path.join(top, *name.split("/")), "rb") as handle:
                found[name] = digest(handle.read().decode("utf-8"))
        return found

    def _own(self):
        """The engine's own files in this copy: all but the list, the shipped text and the tests."""
        return [name for name in _walk(os.path.dirname(self.base)) if name != CODE and name.split("/")[0] not in OUTSIDE]

    def whole(self):
        """Everything this copy lacks, holds changed or holds besides what was shipped."""
        return self.damage() + self.code_damage()

    def code_damage(self):
        """What this copy of the engine lacks or holds changed among its own files, against the
        list the build wrote. A copy that stopped half way is found here."""
        top = os.path.dirname(self.base)
        try:
            with open(os.path.join(top, CODE), "rb") as handle:
                listed = json.loads(handle.read().decode("utf-8"))
            if not isinstance(listed, dict) or not listed:
                raise ValueError(CODE)
        except (OSError, ValueError, UnicodeDecodeError):
            return ["%s is missing or does not read" % CODE]
        found = []
        for name in sorted(listed):
            try:
                with open(os.path.join(top, *name.split("/")), "rb") as handle:
                    if digest(handle.read().decode("utf-8")) != listed[name]:
                        found.append("%s is not the file that was shipped" % name)
            except UnicodeDecodeError:
                found.append("%s does not read as text" % name)
            except OSError:
                found.append("%s is missing" % name)
        found.extend("%s is not a file that was shipped" % name for name in self._own() if name not in listed)
        return found

    def project_text(self, relative):
        return self.read(PROJECT + "/" + relative)
