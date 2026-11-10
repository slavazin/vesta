"""The probe `grep "<regular expression>" <path or glob>`: fires where a line of a matched text file
matches the expression.

It reads at most 2,000 files, skips the directories the configuration tells it to, files over 1 MB and
files that are not UTF-8 text, and tests the first 2,000 characters of each line.
"""
from __future__ import annotations

import re

from kernel import glob
from matchers import paths
from model.abstractions import Matcher, MatchError

FORM = re.compile(r'"([^"]*)"\s+(\S.*)\Z')
MAX_EXPRESSION = 200
MAX_FILES = 2000
MAX_BYTES = 1024 * 1024
MAX_LINE = 2000


class GrepProbe(Matcher):
    id = "grep"

    def __init__(self):
        self.skipped = 0

    def parse(self, subject):
        """(compiled expression, path or glob). Raises MatchError where the probe does not read."""
        found = FORM.match(subject.strip())
        if not found:
            raise MatchError('a grep probe is written `grep "<expression>" <path or glob>`, the expression between double quotes with no `"` inside it')
        expression, target = found.group(1), found.group(2).strip()
        if len(expression) > MAX_EXPRESSION:
            raise MatchError("the expression is %d characters; the most is %d" % (len(expression), MAX_EXPRESSION))
        try:
            compiled = re.compile(expression)
        except re.error as error:
            raise MatchError("the expression does not read as a regular expression (%s)" % error)
        return compiled, paths.inside(target)

    def match(self, subject, context):
        expression, target = self.parse(subject)
        self.skipped = 0
        tree = context.tree
        for path in self._files(tree, target, context.config.ignore):
            size = tree.size(path)
            if size is None or size > MAX_BYTES:
                self.skipped += 1
                continue
            try:
                text = tree.read(path)
            except (UnicodeDecodeError, OSError):
                self.skipped += 1
                continue
            for line in text.split("\n"):
                if expression.search(line[:MAX_LINE]):
                    return True
        return False

    def _files(self, tree, target, ignore):
        """The files a path or a glob names. A plain path that is not there cannot be evaluated."""
        if not glob.has_wildcard(target):
            paths.guarded(tree, target)
            if tree.is_file(target):
                return [target]
            if not tree.is_dir(target):
                raise MatchError("there is no `%s` to read" % target)
            target = target + "/**"
        parts = target.split("/")
        literal = []
        for part in parts:
            if glob.has_wildcard(part):
                break
            literal.append(part)
        skipped = [part for part in literal if part in ignore]
        if skipped:
            raise MatchError("`%s` is a folder the engine is told to skip (`changes.ignore` in vesta/vesta.yml), so the probe cannot read it" % skipped[0])
        if literal:
            paths.guarded(tree, "/".join(literal))
        found = []
        self._walk(tree, "/".join(literal), target, set(ignore), found)
        return found

    def _walk(self, tree, folder, pattern, ignore, found):
        for name in tree.list(folder):
            path = (folder + "/" + name) if folder else name
            if tree.leaves_root(path):
                self.skipped += 1
            elif tree.is_dir(path):
                if name not in ignore and not tree.is_link(path):
                    self._walk(tree, path, pattern, ignore, found)
            elif glob.match(pattern, path):
                if len(found) >= MAX_FILES:
                    raise MatchError("the probe reaches more than %d files; name a narrower path" % MAX_FILES)
                found.append(path)


MEMBER = GrepProbe
