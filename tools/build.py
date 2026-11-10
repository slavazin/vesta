"""The build: refresh the test data from the specification, and copy the engine into the init skill.

Usage: python3 tools/build.py [--root <dir>]

1. Where the specification folder is present, copy its terms list and the verbatim text blocks of its
   templates file into engine/tests/data/. Where it is absent this step is skipped: the data is already
   in the repository.
2. Write engine/templates/shipped.json and engine/files.json, the fingerprints of every shipped text
   file and of every file of the engine itself.
3. Copy engine/ (without its tests and bytecode) to skills/vesta-init/engine/.
"""
from __future__ import annotations

import os
import shutil
import sys

SPEC = "spec"
TERMS = "neutrality-terms.txt"
TEMPLATES = "06-templates.md"
FENCE = "````"
OPEN = FENCE + "markdown"

# The verbatim blocks of the templates file, in the order they occur: output name, expected first line.
VERBATIM = [
    ("language.md", "# Writing rules"),
    ("walks-start.md", "# Start walk"),
    ("walks-close.md", "# Close walk"),
    ("walks-learn.md", "# Learn walk"),
    ("pointer-block.md", "<!-- vesta:start -->"),
    ("decision-example-2.md", "---"),
]

# The record examples of the stores file: three-backtick `markdown` blocks that open with a frontmatter mark.
ARCHITECTURE = "02-architecture.md"
STORES = "03-stores-and-schemas.md"
EXAMPLES = ["decision-example-1.md", "observation-example-1.md"]

SKIP_IN_COPY = ("tests", "__pycache__", "*.pyc", ".DS_Store")


def blocks(text, fence=FENCE, tag="markdown"):
    """Return the content of every block of that tag fenced by exactly that fence, in order.
    A block inside a longer fence is not taken."""
    found = []
    current = None
    outer = None
    for line in text.replace("\r\n", "\n").split("\n"):
        if outer is not None:
            if line == outer:
                outer = None
            continue
        if current is None:
            if line == fence + tag:
                current = []
            elif line.startswith(fence + "`"):
                outer = line[:len(line) - len(line.lstrip("`"))]
        elif line == fence:
            found.append("\n".join(current) + "\n")
            current = None
        else:
            current.append(line)
    if current is not None:
        raise ValueError("a %s block is not closed" % OPEN)
    return found


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def refresh_test_data(root):
    """Copy the terms list and the verbatim blocks into engine/tests/data/. Return the paths written."""
    spec = os.path.join(root, SPEC)
    if not os.path.isdir(spec):
        return []
    data = os.path.join(root, "engine", "tests", "data")
    written = []
    if os.path.isdir(os.path.join(data, "verbatim")):
        shutil.rmtree(os.path.join(data, "verbatim"))
    with open(os.path.join(spec, TERMS), encoding="utf-8") as handle:
        write(os.path.join(data, TERMS), handle.read().replace("\r\n", "\n"))
    written.append(os.path.join(data, TERMS))
    with open(os.path.join(spec, TEMPLATES), encoding="utf-8") as handle:
        found = blocks(handle.read())
    if len(found) != len(VERBATIM):
        raise ValueError("%s holds %d verbatim blocks; %d are named here" % (TEMPLATES, len(found), len(VERBATIM)))
    for (name, first), text in zip(VERBATIM, found):
        if text.split("\n", 1)[0] != first:
            raise ValueError("the block for %s opens %r, not %r" % (name, text.split("\n", 1)[0], first))
        path = os.path.join(data, "verbatim", name)
        write(path, text)
        written.append(path)
    stores = os.path.join(spec, STORES)
    if os.path.isfile(stores):
        with open(stores, encoding="utf-8") as handle:
            records = [text for text in blocks(handle.read(), FENCE[:3]) if text.startswith("---\n")]
        if len(records) != len(EXAMPLES):
            raise ValueError("%s holds %d record examples; %d are named here" % (STORES, len(records), len(EXAMPLES)))
        for name, text in zip(EXAMPLES, records):
            path = os.path.join(data, "verbatim", name)
            write(path, text)
            written.append(path)
    architecture = os.path.join(spec, ARCHITECTURE)
    if os.path.isfile(architecture):
        with open(architecture, encoding="utf-8") as handle:
            configs = [text for text in blocks(handle.read(), FENCE[:3], "yaml") if text.startswith("schema: ")]
        if len(configs) != 1:
            raise ValueError("%s holds %d configuration blocks; one is expected" % (ARCHITECTURE, len(configs)))
        path = os.path.join(data, "verbatim", "vesta.yml")
        write(path, configs[0])
        written.append(path)
    return written


def _shipping(root):
    """The engine's own module that fingerprints its files, loaded from the tree being built."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("vesta_build_shipped", os.path.join(root, "engine", "kernel", "shipped.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_lists(root):
    """Write engine/templates/shipped.json, the fingerprint of every shipped text file, and
    engine/files.json, the fingerprint of every file of the engine itself, so that a copy of the
    engine can tell whether it is whole. Returns the two counts."""
    shipping = _shipping(root)
    shipped = shipping.Shipped(os.path.join(root, "engine"))
    texts, code = shipped.fingerprints(), shipped.code()
    write(os.path.join(shipped.base, shipping.LIST), shipping.listing(texts))
    write(os.path.join(root, "engine", shipping.CODE), shipping.listing(code))
    return len(texts), len(code)


def copy_engine(root):
    """Replace skills/vesta-init/engine/ with a copy of engine/, less tests and bytecode."""
    source = os.path.join(root, "engine")
    target = os.path.join(root, "skills", "vesta-init", "engine")
    if os.path.isdir(target):
        shutil.rmtree(target)
    shutil.copytree(source, target, ignore=shutil.ignore_patterns(*SKIP_IN_COPY))
    return target


def main(argv):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    args = list(argv)
    if args[:1] == ["--root"] and len(args) == 2:
        root = os.path.abspath(args[1])
    elif args:
        sys.stderr.write(__doc__)
        return 2
    written = refresh_test_data(root)
    if written:
        print("test data: %d files refreshed under engine/tests/data/" % len(written))
    else:
        print("test data: no specification folder; left as it is")
    texts, code = write_lists(root)
    print("shipped list: %d files named in engine/templates/shipped.json" % texts)
    print("engine list: %d files named in engine/files.json" % code)
    print("engine copy: %s" % os.path.relpath(copy_engine(root), root).replace(os.sep, "/"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
