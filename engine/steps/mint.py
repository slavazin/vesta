"""The `mint` step: where the rules for an observation are, and the shape `obs add` reads."""
from __future__ import annotations

from session import observations
from steps.base import TextStep

LANGUAGE = "vesta/language.md"


class MintStep(TextStep):
    id = "mint"
    title = "Mint"

    def data(self, context):
        stores = observations.stores_of(context)
        if not stores:
            return ["This project has no store that takes observations, so there is nothing to send."]
        lines = []
        for store in stores:
            option = " --store %s" % store.name if len(stores) > 1 else ""
            lines.append("How to write one: `%s`." % observations.schema_path(store))
            lines.append("`obs add%s` reads a JSON array on standard input, one item for each observation:" % option)
            lines.extend(["", "```json", "[", "  " + observations.shape(store), "]", "```", ""])
        lines.append("The engine fills the rest: the id, the date, the session, and where the observation stands.")
        return lines

    def words(self, context):
        return {"language": "`%s`" % LANGUAGE}


MEMBER = MintStep
