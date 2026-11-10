"""The `layout` check: every store folder has its two files, and no index is stored."""
from __future__ import annotations

from kernel.finding import ERROR, Finding
from model import config
from model.abstractions import Check

README = "README.md"
SCHEMA = "SCHEMA.md"
STORED_INDEX = ("index.md", "index.json", "index.yml")


class LayoutCheck(Check):
    id = "layout"
    residue = "not what a README or a SCHEMA says, beyond the schema block reading"

    def run(self, context):
        found = []
        tree = context.tree
        folders = [config.HOME]
        for name, settings in context.config.stores.items():
            folders.append(settings.path)
            if not tree.is_dir(settings.path):
                found.append(Finding(ERROR, self.id, settings.path, 1, "the folder of the store `%s` is missing" % name))
                continue
            if not tree.is_file(settings.path + "/" + README):
                found.append(Finding(ERROR, self.id, settings.path + "/" + README, 1, "the store `%s` has no %s" % (name, README)))
            schema = settings.path + "/" + SCHEMA
            if not tree.is_file(schema):
                found.append(Finding(ERROR, self.id, schema, 1, "the store `%s` has no %s" % (name, SCHEMA)))
            for line, message in context.stores.unreadable.get(name, []):
                found.append(Finding(ERROR, self.id, schema, line, message))
            store = context.stores.get(name)
            if store is not None and settings.recall == "index" and store.type.role_field("when") is None:
                found.append(Finding(
                    ERROR, self.id, schema, 1,
                    "the store `%s` has `recall: index` and its schema block names no field for the index role `when`" % name,
                ))
            for stray in self._strays(tree, settings, store):
                found.append(Finding(ERROR, self.id, stray, 1, "this file is in the folder of the store `%s` and is not where a record of it lives; the engine does not read it" % name))
        for folder in folders:
            for name in tree.list(folder):
                if name.lower() in STORED_INDEX:
                    found.append(Finding(
                        ERROR, self.id, folder + "/" + name, 1,
                        "an index is stored here; the index is computed each time it is asked for and never kept",
                    ))
        return found


    def _strays(self, tree, settings, store):
        """Markdown files in a store's folder that the store does not read as records."""
        if store is None:
            return []
        known = set(store.paths())
        return [
            path for path in tree.walk(settings.path)
            if path.lower().endswith(".md") and path not in known
            and path.rsplit("/", 1)[-1].lower() not in ("readme.md", "schema.md", "index.md")
            and "." not in path.rsplit("/", 1)[-1][:-3]
        ]


MEMBER = LayoutCheck
