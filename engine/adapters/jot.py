"""The `jot` capture source: the owner's corrections as the session noted them with `jot --steer`."""
from __future__ import annotations

from model.abstractions import CaptureSource


class JotCapture(CaptureSource):
    id = "jot"

    def steers(self, session):
        """[{at, text, anchor}] for each jot of the session marked as a steer, in order."""
        return [
            {"at": jot.get("at", ""), "text": jot.get("text", ""), "anchor": jot.get("anchor", "")}
            for jot in session.jots if jot.get("steer")
        ]


MEMBER = JotCapture
