"""The configuration reader: `vesta/vesta.yml`, a register in the YAML subset.

`load` builds a Config, filling every key the file leaves out with its schema-1 value, so a key added
later never turns a feature on. `problems` lists what is wrong with the file for the `config` check.
"""
from __future__ import annotations

from kernel import yamlsubset
from kernel.errors import SubsetError, UsageError
from kernel.version import SCHEMA

PATH = "vesta/vesta.yml"
HOME = "vesta"
LEVELS = ("quiet", "standard", "active")
AUTO = "auto"

import re

TEXT, INT, BOOL = "text", "a whole number, zero or more", "true or false"
PREFIX = re.compile(r"[A-Za-z][A-Za-z0-9]*\Z")

# The shape of the file: a mapping of known keys. ("each", shape) is a mapping whose keys the project names.
SHAPE = {
    "schema": INT,
    "owner": TEXT,
    "pointer-file": TEXT,
    "engagement": LEVELS,
    "stores": ("each", {
        "path": TEXT,
        "kind": ("ledger", "register"),
        "recall": ("index", "none"),
        "governed": BOOL,
        "label": {"prefix": TEXT, "digits": INT},
    }),
    "checkpoints": ("each", {"walk": TEXT, "steps": [TEXT], "short": [TEXT]}),
    "recall": {"long-index-at": INT},
    "reminders": {
        "learn": {"enabled": BOOL, "open-observations": INT, "sessions-since-pass": INT},
        "pending-proposals": {"enabled": BOOL},
        "unreviewed": {"enabled": BOOL, "sessions": INT},
    },
    "adapters": {"changes": TEXT, "capture": [TEXT]},
    "changes": {"ignore": [TEXT]},
    "proposals": {"kinds": [TEXT]},
    "checks": {"run": [TEXT]},
}


# The keys an owner may ask to have changed without reading this file, each with what it does, in the
# order they are listed. `*` stands for each name the project has under that key.
MEANS = (
    ("engagement", "how much the agent asks, tells and offers"),
    ("owner", "the name recorded when a proposal is approved; empty records none"),
    ("reminders.learn.enabled", "whether the start of a task says that notes have built up and `/vesta-learn` is due"),
    ("reminders.learn.open-observations", "how many open notes it takes for that reminder; 0 leaves this count out"),
    ("reminders.learn.sessions-since-pass", "how many reviewed tasks since the last `/vesta-learn` it takes for that reminder; 0 leaves this count out"),
    ("reminders.pending-proposals.enabled", "whether the start of a task lists the proposals waiting for a decision"),
    ("reminders.unreviewed.enabled", "whether the start of a task says that tasks ended without a review"),
    ("reminders.unreviewed.sessions", "how many such tasks it takes for that reminder"),
    ("recall.long-index-at", "the number of records at which the start of a task says their list is long"),
    ("adapters.changes", "how the files a task changed are found: `auto`, `git` or `mtime`"),
    ("changes.ignore", "the folder names left out when changed files are looked for"),
    ("stores.*.label.prefix", "the letters a record's label opens with; changing it renames every record of the store"),
    ("stores.*.label.digits", "the fewest digits of the number in a label; 0 names a record by its date instead"),
    ("checkpoints.*.steps", "the steps of the walk, in order; one left out is no longer printed"),
    ("checkpoints.*.short", "the steps of the walk's short form"),
)


def offered(data):
    """[(dotted key, what it does, the shape of its value)] for every key of MEANS as this project's file has it."""
    found = []
    for pattern, means in MEANS:
        parts = pattern.split(".")
        names = [parts]
        if "*" in parts:
            at = parts.index("*")
            names = [parts[:at] + [name] + parts[at + 1:] for name, entry in _mapping(data.get(parts[0])).items() if isinstance(entry, dict)]
        for path in names:
            shape = SHAPE
            for part in path:
                shape = shape[1] if isinstance(shape, tuple) and shape and shape[0] == "each" else shape[part]
            found.append((".".join(path), means, shape))
    return found


def held(data, dotted):
    """(the value a dotted key holds in the file, whether the file names it)."""
    here = data
    for part in dotted.split("."):
        if not isinstance(here, dict) or part not in here:
            return None, False
        here = here[part]
    return here, True


def takes(shape):
    """What a value of that shape is, in words."""
    return _describe(shape)


def shown(value):
    return _show(value) if value != "" else "(empty)"


def parsed(shape, text):
    """The value a text names for a key of that shape. Raises ValueError with what it must be."""
    text = text.strip()
    if shape == INT:
        if not re.match(r"[0-9]{1,9}\Z", text):
            raise ValueError(INT)
        return int(text)
    if shape == BOOL:
        if text not in ("true", "false"):
            raise ValueError(BOOL)
        return text == "true"
    if isinstance(shape, list):
        inner = text[1:-1] if text.startswith("[") and text.endswith("]") else text
        items = [item.strip() for item in inner.split(",") if item.strip()]
        if any(not re.match(r"[A-Za-z0-9_.@/-]+\Z", item) for item in items):
            raise ValueError("a list of names with commas between them, as `a, b, c`")
        return items
    if isinstance(shape, tuple):
        if text not in shape:
            raise ValueError(_describe(shape))
        return text
    if "\n" in text or len(text) > 200 or text == "-":
        raise ValueError("one line of text, 200 characters at the most, and not `-` alone")
    return text


class StoreConfig(object):
    """One entry of `stores`."""

    def __init__(self, name, entry):
        label = entry.get("label") if isinstance(entry.get("label"), dict) else {}
        self.name = name
        self.path = HOME + "/" + _folder(entry.get("path"), name)
        self.kind = _text(entry.get("kind"), "ledger")
        self.recall = _text(entry.get("recall"), "none")
        self.governed = entry.get("governed") is True
        prefix = _text(label.get("prefix"), "")
        self.prefix = prefix if PREFIX.match(prefix) else (name[:1].upper() or "R")
        self.digits = label.get("digits") if _is_int(label.get("digits")) and label.get("digits") >= 0 else 3


class Checkpoint(object):
    """One entry of `checkpoints`."""

    def __init__(self, name, entry):
        self.id = name
        self.walk = HOME + "/" + _folder(entry.get("walk"), "walks/%s.md" % name)
        self.steps = _texts(entry.get("steps"))
        self.short = _texts(entry.get("short"))


class Config(object):
    """The configuration, with schema-1 values for every key the file leaves out."""

    def __init__(self, data):
        self.data = data
        self.schema = data.get("schema") if _is_int(data.get("schema")) else SCHEMA
        self.owner = _text(data.get("owner"), "")
        self.pointer_file = _text(data.get("pointer-file"), "")
        self.engagement = data.get("engagement") if data.get("engagement") in LEVELS else "standard"
        self.stores = {}
        for name, entry in _mapping(data.get("stores")).items():
            if isinstance(entry, dict):
                self.stores[name] = StoreConfig(name, entry)
        self.checkpoints = {}
        for name, entry in _mapping(data.get("checkpoints")).items():
            if isinstance(entry, dict):
                self.checkpoints[name] = Checkpoint(name, entry)
        self.long_index_at = _int(_mapping(data.get("recall")).get("long-index-at"), 60)
        reminders = _mapping(data.get("reminders"))
        learn = _mapping(reminders.get("learn"))
        self.remind_learn = learn.get("enabled", True) is True
        self.remind_open_observations = _int(learn.get("open-observations"), 25)
        self.remind_sessions_since_pass = _int(learn.get("sessions-since-pass"), 0)
        self.remind_pending = _mapping(reminders.get("pending-proposals")).get("enabled", True) is True
        unreviewed = _mapping(reminders.get("unreviewed"))
        self.remind_unreviewed = _int(unreviewed.get("sessions"), 2) if unreviewed.get("enabled", True) is True else 0
        adapters = _mapping(data.get("adapters"))
        self.changes = _text(adapters.get("changes"), AUTO)
        self.capture = _texts(adapters.get("capture"))
        self.ignore = _texts(_mapping(data.get("changes")).get("ignore"))
        self.kinds = _texts(_mapping(data.get("proposals")).get("kinds"))
        self.checks = _texts(_mapping(data.get("checks")).get("run"))

    def level_reached(self, level):
        """Say whether the configured engagement is at or above a level."""
        if level not in LEVELS:
            return False
        return LEVELS.index(level) <= LEVELS.index(self.engagement)


def _folder(value, default):
    """A path under `vesta/` from the configuration; one that would leave the folder falls back to
    the default, and `problems` reports it."""
    value = _text(value, default)
    return value.strip("/") if inside(value) else default


def inside(value):
    """Say whether a configured path names a place under `vesta/`."""
    parts = value.replace("\\", "/").strip("/").split("/")
    return bool(value.strip("/")) and not value.startswith("/") and all(part not in ("", ".", "..") and ":" not in part for part in parts)


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _int(value, default):
    return value if _is_int(value) else default


def _text(value, default):
    return value if isinstance(value, str) else default


def _texts(value):
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _mapping(value):
    return value if isinstance(value, dict) else {}


def load(text, file=PATH):
    """Read the configuration. Raises UsageError where it does not parse or needs a newer engine."""
    try:
        data = yamlsubset.read(text, file)
    except SubsetError as error:
        raise UsageError("the configuration does not read: %s" % error)
    config = Config(data)
    if config.schema > SCHEMA:
        raise UsageError(
            "this folder is at schema %d and this engine reads up to %d; run `/vesta-init upgrade`" % (config.schema, SCHEMA)
        )
    return config


def _show(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return "a mapping" if isinstance(value, dict) else "[" + ", ".join(str(item) for item in value) + "]"
    return str(value)


def _describe(shape):
    if isinstance(shape, tuple) and shape and shape[0] != "each":
        return "one of " + ", ".join(shape)
    if isinstance(shape, list):
        return "a list of text"
    if isinstance(shape, (dict, tuple)):
        return "a mapping"
    return shape


def _fits(value, shape):
    if shape == TEXT:
        return isinstance(value, str)
    if shape == INT:
        return _is_int(value) and value >= 0
    if shape == BOOL:
        return isinstance(value, bool)
    if isinstance(shape, list):
        return isinstance(value, list) and all(isinstance(item, str) for item in value)
    if isinstance(shape, tuple) and shape[0] != "each":
        return value in shape
    return isinstance(value, dict)


def _walk(data, shape, path, found):
    for key, value in data.items():
        here = path + (key,)
        if key not in shape:
            found.append((here, "the key `%s` is not a key of the configuration" % ".".join(here)))
            continue
        expected = shape[key]
        if not _fits(value, expected):
            found.append((here, "`%s` is `%s`; it must be %s" % (".".join(here), _show(value), _describe(expected))))
        elif isinstance(expected, dict):
            _walk(value, expected, here, found)
        elif isinstance(expected, tuple) and expected[0] == "each":
            for name, entry in value.items():
                if isinstance(entry, dict):
                    _walk(entry, expected[1], here + (name,), found)
                else:
                    found.append((here + (name,), "`%s` is a mapping" % ".".join(here + (name,))))


def problems(text, known):
    """What is wrong with a configuration text: [(line, message)].

    `known` maps `steps`, `kinds`, `checks`, `changes` and `capture` to the ids the manifest holds.
    """
    try:
        data = yamlsubset.read(text, PATH)
    except SubsetError as error:
        return [(error.line, error.message)]
    found = []
    if "schema" not in data:
        found.append((("schema",), "the key `schema` is missing"))
    elif _is_int(data["schema"]) and data["schema"] < 1:
        found.append((("schema",), "`schema` is `%d`; it is 1 or more" % data["schema"]))
    _walk(data, SHAPE, (), found)
    config = Config(data)
    seen, prefixes = {}, {}
    for name, entry in _mapping(data.get("stores")).items():
        if not isinstance(entry, dict):
            continue
        path = entry.get("path")
        if isinstance(path, str) and not inside(path):
            found.append((("stores", name, "path"), "`stores.%s.path` is `%s`; it must name a folder under vesta/" % (name, path)))
        elif isinstance(path, str):
            if path.strip("/") in seen:
                found.append((("stores", name, "path"), "`stores.%s.path` is `%s`, which is also the folder of the store `%s`" % (name, path, seen[path.strip("/")])))
            seen.setdefault(path.strip("/"), name)
        label = entry.get("label")
        prefix = label.get("prefix") if isinstance(label, dict) else None
        if isinstance(prefix, str) and not PREFIX.match(prefix):
            found.append((("stores", name, "label", "prefix"), "`stores.%s.label.prefix` is `%s`; it must be letters and digits, opening with a letter" % (name, prefix)))
        elif isinstance(prefix, str):
            if prefix in prefixes:
                found.append((("stores", name, "label", "prefix"), "`stores.%s.label.prefix` is `%s`, which is also the prefix of the store `%s`; a label must name one record" % (name, prefix, prefixes[prefix])))
            prefixes.setdefault(prefix, name)
    for name, entry in _mapping(data.get("checkpoints")).items():
        walk = entry.get("walk") if isinstance(entry, dict) else None
        if isinstance(walk, str) and not inside(walk):
            found.append((("checkpoints", name, "walk"), "`checkpoints.%s.walk` is `%s`; it must name a file under vesta/" % (name, walk)))

    pointer = data.get("pointer-file")
    if isinstance(pointer, str) and pointer and not inside(pointer):
        found.append((("pointer-file",), "`pointer-file` is `%s`; it must name a file inside the project, written from the project root" % pointer))

    def named(path, ids, table, what):
        for item in sorted(set(ids)):
            if ids.count(item) > 1:
                found.append((path, "`%s` names `%s` %d times; name it once" % (".".join(path), item, ids.count(item))))
            if item not in known.get(table, ()):
                found.append((path, "`%s` names %s `%s`, which this engine does not have" % (".".join(path), what, item)))

    for name, checkpoint in config.checkpoints.items():
        named(("checkpoints", name, "steps"), checkpoint.steps, "steps", "the step")
        named(("checkpoints", name, "short"), checkpoint.short, "steps", "the step")
        for step in checkpoint.short:
            if step not in checkpoint.steps:
                found.append((("checkpoints", name, "short"), "`checkpoints.%s.short` names `%s`, which is not among its steps" % (name, step)))
    named(("proposals", "kinds"), config.kinds, "kinds", "the proposal kind")
    named(("checks", "run"), config.checks, "checks", "the check")
    named(("adapters", "capture"), config.capture, "capture", "the capture source")
    if config.changes != AUTO:
        named(("adapters", "changes"), [config.changes], "changes", "the change source")
    return [(yamlsubset.line_of(text, path), message) for path, message in found]
