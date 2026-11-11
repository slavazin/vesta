"""The neutrality check: no shipped file holds a string from the terms list.

Usage: python3 tools/neutrality.py [--root <dir>] [--terms <file>]

A maintainer keeps a list of strings that must not appear in what is shipped: names of other projects,
of people, of private sources. That list is private and is not in the repository. It is read from
engine/tests/data/neutrality-terms.txt, which version control ignores, or from the file `--terms` names.
Without a list nothing is checked, and the output says so.

A plain line is one term, matched as a whole word without regard to case. A line opening "re:" is a
regular expression, matched with regard to case. Exits 1 and prints `<file>:<line>: <term>` for every
match; exits 0 where there is none; exits 2 where the file `--terms` names is not there.
"""
from __future__ import annotations

import os
import re
import sys

# The specification, git's own folder, the test data, and an editor's settings: none of them is published.
EXEMPT_DIRS = ("spec", ".git", "engine/tests/data", ".idea", ".vscode")
EXEMPT_FILES = ("LICENSE",)
LITTER = (".pyc", ".DS_Store")
RESIDUE = "residue: reads the listed strings only; a paraphrase, a plural or a new name is not found."


def default_terms(root):
    """Where a maintainer's private list sits; version control ignores the file."""
    return os.path.join(root, "engine", "tests", "data", "neutrality-terms.txt")


def read_terms(path):
    """Return [(label, compiled pattern)] from a terms file.

    A plain term matches where no letter touches it on either side, so a term joined to other words
    by `_`, `-` or a digit is still found. The words of a term of several words may be parted by
    spaces, tabs, hyphens or underscores.
    """
    terms = []
    with open(path, encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("re:"):
                terms.append((line, re.compile(line[3:])))
            else:
                words = [re.escape(word) for word in line.split()]
                pattern = r"(?<![^\W\d_])" + r"[\s_-]+".join(words) + r"(?![^\W\d_])"
                terms.append((line, re.compile(pattern, re.IGNORECASE)))
    return terms


def exempt(rel):
    """Say whether a path relative to the root, with `/` separators, is outside the scan."""
    if rel in EXEMPT_FILES:
        return True
    for folder in EXEMPT_DIRS:
        if rel == folder or rel.startswith(folder + "/"):
            return True
    return False


def files(root):
    """Yield every scanned file's path relative to the root, sorted. Compiled bytecode and the
    file manager's own files are not shipped and are left out."""
    found = []
    for folder, names, leaves in os.walk(root):
        rel_folder = os.path.relpath(folder, root).replace(os.sep, "/")
        rel_folder = "" if rel_folder == "." else rel_folder
        names[:] = [name for name in names if not exempt((rel_folder + "/" + name) if rel_folder else name)]
        for leaf in leaves:
            rel = (rel_folder + "/" + leaf) if rel_folder else leaf
            if not exempt(rel) and not leaf.endswith(LITTER):
                found.append(rel)
    return sorted(found)


def scan(root, terms):
    """Return ([(file, line number, what was found)], files read) over the root. A file's own path
    is read as its line 0; a file that is not UTF-8 text is itself a finding."""
    hits = []
    read = 0
    for rel in files(root):
        read += 1
        for label, pattern in terms:
            if pattern.search(rel):
                hits.append((rel, 0, label + " (in the path)"))
        try:
            with open(os.path.join(root, rel), encoding="utf-8") as handle:
                lines = handle.read().splitlines()
        except (UnicodeDecodeError, OSError):
            hits.append((rel, 0, "not UTF-8 text, so it cannot be read for terms"))
            continue
        for number, line in enumerate(lines, 1):
            for label, pattern in terms:
                if pattern.search(line):
                    hits.append((rel, number, label))
    return hits, read


def main(argv):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    terms_path = None
    args = list(argv)
    while args:
        flag = args.pop(0)
        if flag == "--root" and args:
            root = os.path.abspath(args.pop(0))
        elif flag == "--terms" and args:
            terms_path = args.pop(0)
        else:
            sys.stderr.write(__doc__)
            return 2
    if terms_path is None:
        terms_path = default_terms(root)
        if not os.path.isfile(terms_path):
            print("neutrality: no terms list at %s; nothing was checked." % os.path.relpath(terms_path, root).replace(os.sep, "/"))
            return 0
    if not os.path.isfile(terms_path):
        sys.stderr.write("neutrality: no terms file at %s.\n" % terms_path)
        return 2
    hits, read = scan(root, read_terms(terms_path))
    for rel, number, label in hits:
        print("%s:%d: %s" % (rel, number, label))
    print("neutrality: %d files read, %d matches." % (read, len(hits)))
    print(RESIDUE)
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
