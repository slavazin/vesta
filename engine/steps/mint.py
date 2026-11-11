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
            card, lacking = observations.card(context, store)
            lines.append("How to write one, from `%s`. It holds for every observation prepared on this sheet, whichever section asked for it:" % observations.schema_path(store))
            lines.extend([""] + card)
            if lacking:
                lines.extend(["`%s` has no section %s to print here: read the file for how an observation is written." % (
                    observations.schema_path(store), " or ".join("*%s*" % name for name in lacking)), ""])
            lines.append("`obs add%s` reads a JSON array on standard input, one item for each observation:" % option)
            lines.extend(["", "```json", "[", "  " + observations.shape(store), "]", "```", ""])
        lines.append("The engine fills the rest: the id, the date, the session, and where the observation stands.")
        return lines

    def words(self, context):
        session = context.walk.session
        reading = session.origin is not None
        return {
            "language": "`%s`" % LANGUAGE,
            "added": " with `--session %s` added" % session.id if reading else "",
            "option": " --session %s" % session.id if reading else "",
            "jots": "" if reading else " A jot in the bundle that no prepared observation covers is sent as one, with `via: jot`.",
        }


MEMBER = MintStep
