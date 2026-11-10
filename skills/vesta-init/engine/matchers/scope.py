"""Scope match: a record governs a path where one of its path prefixes covers it, segment by segment."""
from __future__ import annotations

from model.abstractions import Matcher


def _segments(path):
    return [part for part in path.replace("\\", "/").split("/") if part not in ("", ".")]


def covers(scope, path):
    """`src/http` covers `src/http/client.py` and not `src/httpx/a.py`."""
    wanted, given = _segments(scope), _segments(path)
    return bool(wanted) and given[:len(wanted)] == wanted


def reaches(scope, query):
    """Say whether a query matches a scope: the scope covers it, or the query ends `/` and the scope lies inside it."""
    if covers(scope, query):
        return True
    if query.replace("\\", "/").endswith("/"):
        inside, outer = _segments(scope), _segments(query)
        return inside[:len(outer)] == outer
    return False


class ScopeMatcher(Matcher):
    """The mechanical match of a record's path prefixes against one path."""

    id = "scope"

    def match(self, subject, context=None):
        scopes, path = subject
        return any(reaches(scope, path) for scope in scopes)


MEMBER = ScopeMatcher


def matching(store, paths):
    """The accepted records of a store whose paths role reaches one of the paths, in label order."""
    matcher = ScopeMatcher()
    found = []
    if store.type.role_field("paths") is None:
        return found
    for record in store.list():
        if not store.type.is_accepted(record):
            continue
        scopes = record.texts(store.type.role_field("paths"))
        if any(matcher.match((scopes, path)) for path in paths):
            found.append(record)
    return found
