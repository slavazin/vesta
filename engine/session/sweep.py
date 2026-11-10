"""The sweep: the records in force that cover a path the session changed and that it never loaded."""
from __future__ import annotations

from matchers import scope
from session import state


def missed(context, session):
    """([(store, record)] in store and label order, why the changed paths could not be read)."""
    paths, problem = state.changed(context, session)
    found = []
    if problem or not paths:
        return found, problem
    for store in context.stores.recalled():
        for record in scope.matching(store, paths):
            if session.entry(record) is None:
                found.append((store, record))
    return found, ""


def loaded(context, session):
    """[(store, record)] for each record of the loaded list that is still in a store, in the order loaded."""
    found = []
    for entry in session.loaded:
        named = context.stores.resolve(entry.get("record", ""))
        if named is not None:
            found.append(named)
    return found
