"""The admitted-hash file: the fingerprint of every governed file as last approved."""
from __future__ import annotations

import json

from kernel.shipped import digest  # noqa: F401  (used by callers as admitted.digest)
from model import config as configuration

PATH = "vesta/log/admitted.json"
LANGUAGE = "vesta/language.md"
SCHEMA = "SCHEMA.md"


def governed_paths(tree, config, stores):
    """Every governed file that exists: the records of governed stores, the walk files, the writing
    rules, the configuration and every SCHEMA.md. Sorted."""
    found = set()
    for path in (LANGUAGE, configuration.PATH):
        if tree.is_file(path):
            found.add(path)
    for checkpoint in config.checkpoints.values():
        if tree.is_file(checkpoint.walk):
            found.add(checkpoint.walk)
    for name, settings in config.stores.items():
        if tree.is_file(settings.path + "/" + SCHEMA):
            found.add(settings.path + "/" + SCHEMA)
        store = stores.get(name)
        if settings.governed and store is not None:
            found.update(store.paths())
    return sorted(found)


def read(tree):
    """The recorded fingerprints, `{path: hash}`; empty where the file is absent or does not read."""
    if not tree.is_file(PATH):
        return {}
    try:
        data = json.loads(tree.read(PATH))
    except ValueError:
        return {}
    return dict((str(key), str(value)) for key, value in data.items()) if isinstance(data, dict) else {}


def text(hashes):
    return json.dumps(hashes, indent=1, sort_keys=True) + "\n"


def current(tree, config, stores):
    """The fingerprint of every governed file as it stands."""
    return dict((path, digest(tree.read(path))) for path in governed_paths(tree, config, stores))


def record(tree, paths, removed=()):
    """Write the fingerprints of the given paths as they stand, and drop the removed ones."""
    hashes = read(tree)
    for path in paths:
        hashes[path] = digest(tree.read(path))
    for path in removed:
        hashes.pop(path, None)
    tree.write(PATH, text(hashes))
