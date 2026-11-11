"""Fixture projects for the tests: a temporary folder holding a `vesta/` folder."""
import io
import os
import shutil
import tempfile

import support
from cli import build, main
from kernel import yamlsubset
from kernel.clock import FixedClock

TEMPLATES = os.path.join(support.ENGINE, "templates", "vesta")

# The configuration of the members built so far; the shipped file is tested whole from the slice that
# builds its last member.
CONFIG = {
    "schema": 1,
    "owner": "",
    "pointer-file": "",
    "engagement": "standard",
    "stores": {
        "decisions": {
            "path": "decisions", "kind": "ledger", "recall": "index", "governed": True,
            "label": {"prefix": "D", "digits": 3},
        },
    },
    "checks": {"run": ["config", "layout", "records", "lengths"]},
}

NOTES_STORE = {
    "path": "notes", "kind": "ledger", "recall": "index", "governed": True,
    "label": {"prefix": "N", "digits": 2},
}

NOTES_SCHEMA = """# How to write a note

```vesta-schema
layout: flat
title: required
index:
  when: cue
  why: stakes
  except: unless
  paths: areas
  triggers: watch
lifecycle:
  status: state
  retired-because: gone-because
payload-section: Note
conditions: [falsifier-or-trigger, retired-reason]
fields:
  - name: uid
    type: text
    required: true
  - name: id
    type: text
    required: true
  - name: state
    type: enum
    values: [accepted, superseded, retired]
    required: true
    mutable: true
  - name: cue
    type: text
    required: true
    mutable: true
  - name: stakes
    type: text
    mutable: true
  - name: unless
    type: text
    mutable: true
  - name: areas
    type: list
    mutable: true
  - name: watch
    type: triggers
    mutable: true
  - name: gone-because
    type: text
    mutable: true
sections:
  - name: Note
    required: true
```
"""


def decision(label="D-001", uid="00000001", **changes):
    """The fields of a valid decision; keyword arguments replace fields (underscores read as hyphens)."""
    fields = {
        "uid": uid,
        "id": label,
        "status": "accepted",
        "decided": "2026-01-05",
        "approved-by": "A. Reviewer",
        "when": "sending anything to a client",
        "why": "a stale figure goes out",
        "except": "",
        "scopes": [],
        "triggers": [],
        "supersedes": [],
        "superseded-by": "",
        "retired-because": "",
        "related": [],
    }
    for name, value in changes.items():
        fields[name.replace("_", "-")] = value
    return fields


BODY = """# Every figure is checked on the day it is sent

## Context
Reports are drafted over several days.

## Decision
Every figure is checked against the source on the day of sending.

## Warrant
- False if: the source is frozen before drafting starts.
"""


def built_config():
    """The shipped configuration cut down to the members this engine has: the fixture every test of
    an initialized project runs under until the last member is built, when it is the shipped file."""
    from cli import manifest
    known = manifest.known()
    config = yamlsubset.read(support.read(os.path.join(TEMPLATES, "vesta.yml")))
    for checkpoint in config["checkpoints"].values():
        for key in ("steps", "short"):
            if key in checkpoint:
                checkpoint[key] = [step for step in checkpoint[key] if step in known["steps"]]
    config["proposals"]["kinds"] = [kind for kind in config["proposals"]["kinds"] if kind in known["kinds"]]
    config["checks"]["run"] = [check for check in config["checks"]["run"] if check in known["checks"]]
    config["adapters"]["capture"] = [source for source in config["adapters"]["capture"] if source in known["capture"]]
    return config


class Project(object):
    """A project in a temporary folder. Use as a context manager."""

    def __init__(self, config=None, stores=("decisions",), init=False):
        self.temp = tempfile.TemporaryDirectory()
        self.root = os.path.realpath(self.temp.name)
        self.clock = FixedClock()
        # What the commands of this project are told of where they were started: nothing, unless a test says.
        self.environ = {}
        if init:
            self.config = None
            code, out, err = self.run("init")
            assert code == 0, out + err
            self.config = config if config is not None else built_config()
            self.write_config(self.config)
            self.admit("vesta/vesta.yml")
            return
        self.config = config if config is not None else CONFIG
        self.write_config(self.config)
        for name in stores:
            shutil.copytree(os.path.join(TEMPLATES, name), os.path.join(self.root, "vesta", name))

    def admit(self, *paths):
        """Record files as approved, as a test's stand-in for the approval path."""
        from kernel.tree import DiskTree
        from proposals import admitted
        admitted.record(DiskTree(self.root), paths)

    def files(self, under=""):
        """Every file under the root (or a folder of it) with its text, by path."""
        found = {}
        top = self.path(under) if under else self.root
        for folder, names, leaves in os.walk(top):
            names[:] = [name for name in names if name != "__pycache__"]
            for leaf in leaves:
                full = os.path.join(folder, leaf)
                found[os.path.relpath(full, self.root).replace(os.sep, "/")] = support.read(full)
        return found

    def folders(self, under="vesta"):
        found = []
        for folder, names, _ in os.walk(self.path(under)):
            found.extend(os.path.relpath(os.path.join(folder, name), self.root).replace(os.sep, "/") for name in names)
        return sorted(found)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.temp.cleanup()

    def path(self, relative):
        return os.path.join(self.root, *relative.split("/"))

    def write(self, relative, text):
        support.write(self.path(relative), text)

    def read(self, relative):
        return support.read(self.path(relative))

    def write_config(self, config):
        text = config if isinstance(config, str) else yamlsubset.write(config)
        self.write("vesta/vesta.yml", text)

    def add_notes_store(self):
        config = dict(self.config)
        config["stores"] = dict(config["stores"], notes=NOTES_STORE)
        self.config = config
        self.write_config(config)
        self.write("vesta/notes/README.md", "# Notes\n")
        self.write("vesta/notes/SCHEMA.md", NOTES_SCHEMA)

    def context(self, out=None):
        return build.context(self.root, out if out is not None else io.StringIO(), self.clock, environ=self.environ)

    def store(self, name="decisions"):
        return self.context().stores.get(name)

    def put(self, fields, body=BODY, store="decisions", name=None, admit=True):
        """Write a record file from fields and a body, in the canonical form. Returns its path."""
        folder = self.config["stores"][store]["path"] if isinstance(self.config, dict) else store
        relative = "vesta/%s/%s.md" % (folder, name or fields["id"])
        self.write(relative, "---\n" + yamlsubset.write(fields) + "---\n" + body)
        governed = isinstance(self.config, dict) and self.config["stores"][store].get("governed")
        if admit and governed and os.path.isfile(self.path("vesta/log/admitted.json")):
            self.admit(relative)
            line = "- 2026-01-05 · P-000@00000000 · add · %s@%s · approved by A. Reviewer · evidence 0\n" % (fields["id"], fields.get("uid", ""))
            with open(self.path("vesta/log/admissions.md"), "a", encoding="utf-8", newline="\n") as handle:
                handle.write(line)
        return relative

    def run(self, *argv, **options):
        """Run a command in-process. Returns (exit code, standard output, standard error)."""
        out, err = io.StringIO(), io.StringIO()
        options.setdefault("environ", self.environ)
        code = main.main(list(argv), root=self.root, clock=self.clock, out=out, err=err, **options)
        return code, out.getvalue(), err.getvalue()

    def check(self):
        """The finding lines `check` prints."""
        _, out, _ = self.run("check")
        return [line for line in out.split("\n") if line.startswith(("error ", "warning "))]
