"""The `walks` check: the walk files' tables read, and each row and lens is well formed."""
from __future__ import annotations

import re

from kernel import ids
from kernel.finding import ERROR, Finding
from model.abstractions import Check
from stores import walks

DECIDED = "vesta/log/proposals"


class WalksCheck(Check):
    id = "walks"
    residue = "not whether a condition would be recognized, whether a counterfactual bites, or whether a row is still needed"

    def run(self, context):
        found = []
        lens_names = {}
        for name, checkpoint in context.config.checkpoints.items():
            walk = walks.read(context.tree, checkpoint.walk)
            if walk is None:
                found.append(Finding(ERROR, self.id, checkpoint.walk, 1, "the walk file of `%s` is missing" % name))
                continue

            def problem(line, message, path=walk.path):
                found.append(Finding(ERROR, self.id, path, line, message))

            for line, message in walk.problems:
                problem(line, message)
            for step in dict.fromkeys(checkpoint.steps):
                if step not in context.known.get("steps", ()):
                    continue
                for section in context.member("steps", step).reads:
                    if walk.document.section(section) is None:
                        problem(1, "the file has no `## %s` section, which the step `%s` prints" % (section, step))
            seen, acts = set(), {}
            for row in walk.rows:
                line, label = row["line"], row["id"]
                if not re.match(re.escape(name) + r"-[0-9]{2,}\Z", label):
                    problem(line, "the row id `%s` has the form `%s-NN`" % (label, name))
                if label in seen:
                    problem(line, "the row id `%s` occurs twice" % label)
                seen.add(label)
                for column in ("fires-when", "consult", "owed act"):
                    if not row[column]:
                        problem(line, "the row `%s` has no `%s`" % (label, column))
                if len(walks.consult_paths(row["consult"])) > 1:
                    problem(line, "the row `%s` consults more than one thing; a row names exactly one" % label)
                if walks.globs_of(row["fires-on"]) is None:
                    problem(line, "`fires-on` of the row `%s` is `%s`, or globs in backticks separated by commas" % (label, walks.JUDGED))
                if row["owed act"] and row["owed act"] in acts:
                    problem(line, "the rows `%s` and `%s` owe the same act; merge them" % (acts[row["owed act"]], label))
                acts.setdefault(row["owed act"], label)
                self._shared(context, problem, row, "the row `%s`" % label)
            for lens in walk.lenses:
                line, label = lens["line"], lens["lens"]
                if not walks.LENS_NAME.match(label):
                    problem(line, "the lens name `%s` is lower case with hyphens" % label)
                if label in lens_names:
                    problem(line, "the lens `%s` is also in %s; a lens name is used once across the walk files" % (label, lens_names[label]))
                lens_names.setdefault(label, walk.path)
                for column in ("angle", "counterfactual"):
                    if not lens[column]:
                        problem(line, "the lens `%s` has no `%s`" % (label, column))
                self._shared(context, problem, lens, "the lens `%s`" % label)
        return found

    def _shared(self, context, problem, item, what):
        if item["level"] not in walks.LEVELS:
            problem(item["line"], "`level` of %s is one of %s" % (what, ", ".join(walks.LEVELS)))
        origin = item["origin"]
        if origin != walks.SEED:
            label = ids.parse_ref(origin)[0] or origin
            if not context.tree.is_file("%s/%s.md" % (DECIDED, label)):
                problem(item["line"], "`origin` of %s is `%s`; it is `seed`, or a decided proposal under %s/" % (what, origin, DECIDED))


MEMBER = WalksCheck
