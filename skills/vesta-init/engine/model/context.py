"""The context: what a command, a step, a check or an applier is handed. Nothing reaches for a global."""
from __future__ import annotations

from kernel import ids

RECALLED = "index"


class Stores(object):
    """The project's stores by name, and the one place a reference is resolved."""

    def __init__(self):
        self.by_name = {}
        self.unreadable = {}

    def add(self, store):
        self.by_name[store.name] = store

    def names(self):
        return list(self.by_name)

    def all(self):
        return list(self.by_name.values())

    def get(self, name):
        return self.by_name.get(name)

    def recalled(self):
        """The stores whose index joins the start walk."""
        return [store for store in self.all() if store.settings.recall == RECALLED]

    def resolve(self, ref):
        """(store, record) for what names a record in any store, or None.

        The internal id is followed where the reference has one; the label only where it has none.
        """
        label, uid = ids.parse_ref(ref)
        for store in self.all():
            record = store.get(ids.format_ref(label, uid) if label and uid else (uid or label or ""))
            if record is not None and (uid is None or record.uid == uid):
                return store, record
        return None


class Context(object):
    """The root, the tree, the configuration, the stores, the clock, and the ids the manifest holds.

    `services` is how a layer below the command line reaches a member without importing one: the
    command line supplies it. `session` is the session a command resolved, and `walk` the walk a
    sheet is being printed for; both are empty until a command sets them.
    """

    def __init__(self, root, tree, config, stores, clock, known, out, config_text="", shipped=None, services=None, environ=None):
        self.services = services
        # The environment the command was started in, as a mapping; what a harness is told apart by.
        self.environ = environ if environ is not None else {}
        self.session = None
        self.stdin = None
        self.walk = None
        self.root = root
        self.tree = tree
        self.config = config
        self.stores = stores
        self.clock = clock
        self.known = known
        self.out = out
        self.config_text = config_text
        self.shipped = shipped

    def write(self, text=""):
        """Print one line of a command's output."""
        self.out.write(text + "\n")

    def over(self, tree, stores):
        """The same context over another tree, as when a change is tried in an overlay."""
        return Context(self.root, tree, self.config, stores, self.clock, self.known, self.out, self.config_text, self.shipped, self.services, self.environ)

    def member(self, table, name):
        """The class of a member the manifest holds, imported at this moment and not before."""
        return self.services.member(table, name)

    def change_source(self, name=None):
        """(the change source, a note on how it was chosen). With no name, the one the configuration
        puts in effect; with one, the source of that id, as when a base names the source that made it."""
        return self.services.change_source(self, name)
