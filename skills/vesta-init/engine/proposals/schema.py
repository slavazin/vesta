"""The `schema` kind: a store's SCHEMA.md changed by find/replace pairs. A change under which a
record already in the store would fail is refused when the proposal is applied, by the checks."""
from __future__ import annotations

from proposals import targets
from proposals.language import LanguageKind


class SchemaKind(LanguageKind):
    id = "schema"

    def resolve(self, target, context):
        return targets.schema_file(context, target), None


MEMBER = SchemaKind
