"""How the learn walk opens: in the open pass, or in one opened now over the notes open at this moment."""
from __future__ import annotations

from kernel.errors import Refusal, UsageError
from model.abstractions import Opening
from session import passes

class LearnOpening(Opening):
    def open(self, context, options):
        if options.get("session"):
            raise UsageError("a learn pass belongs to no session, so `walk learn` takes no `--session`")
        if options.get("from") and passes.read(context.tree) is None:
            raise Refusal(
                "`--from %s` prints a later part of a learn pass, and no pass is open: the last one was sealed. "
                "`walk learn` opens a new one." % options["from"], passes.RULE,
            )
        found, opened = passes.open_now(context, options.get("ask", ""))
        count = len(found.window)
        if opened:
            said = ["This pass was opened now. It reads the %d note%s open at this moment; a note written later waits for the next pass." % (count, "" if count == 1 else "s")]
        else:
            said = ["This pass was already open, and goes on from where it was left. It reads the %d note%s that were open when it opened." % (count, "" if count == 1 else "s")]
        return found, said


MEMBER = LearnOpening
