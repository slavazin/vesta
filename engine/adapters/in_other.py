"""The `other` harness: any program the engine knows nothing of. It is never found; it is what is
left where no known harness started the command, and what an owner chooses to have nothing assumed."""
from __future__ import annotations

from model.abstractions import Harness


class InOther(Harness):
    id = "other"
    name = "a harness the engine knows nothing of"
    residue = "the engine cannot find its conversations and cannot start a copy of one; saved text is read where the owner names it"

    known = False

    def here(self):
        return False


MEMBER = InOther
