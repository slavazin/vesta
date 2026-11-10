"""The `links` check: what one record says of another resolves, and the paths records and rows name exist."""
from __future__ import annotations

from kernel import glob, yamlsubset
from kernel.finding import ERROR, WARNING, Finding
from model.abstractions import Check
from stores import walks


class LinksCheck(Check):
    id = "links"
    residue = "not whether the thing pointed at says what the pointer claims"

    def run(self, context):
        found = []
        tree = context.tree
        for store in context.stores.all():
            paths_field = store.type.role_field("paths")
            for record in store.list():
                for field in store.type.fields:
                    if field.type not in ("ref", "refs"):
                        continue
                    for text in record.texts(field.name):
                        if context.stores.resolve(text) is None:
                            found.append(Finding(
                                ERROR, self.id, record.path, yamlsubset.line_of(record.front, (field.name,), 2),
                                "`%s` names %s, which is not a record" % (field.name, text),
                            ))
                if paths_field and store.type.is_accepted(record):
                    for path in record.texts(paths_field):
                        if not self._exists(tree, path):
                            found.append(Finding(
                                WARNING, self.id, record.path, yamlsubset.line_of(record.front, (paths_field,), 2),
                                "`%s` names `%s`, which is not in the project" % (paths_field, path),
                            ))
        for checkpoint in context.config.checkpoints.values():
            walk = walks.read(tree, checkpoint.walk)
            if walk is None:
                continue
            for row in walk.rows:
                for path in walks.consult_paths(row["consult"]):
                    if not glob.has_wildcard(path) and not self._exists(tree, path):
                        found.append(Finding(WARNING, self.id, walk.path, row["line"], "the row `%s` consults `%s`, which is not in the project" % (row["id"], path)))
        return found

    def _exists(self, tree, path):
        try:
            return tree.exists(path)
        except ValueError:
            return False


MEMBER = LinksCheck
