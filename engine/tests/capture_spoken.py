"""A capture source that exists only for a test: it reports one correction for every session."""
from model.abstractions import CaptureSource


class Spoken(CaptureSource):
    id = "spoken"

    def steers(self, session):
        return [{"at": "2026-01-05T09:00:00Z", "text": "said aloud: keep the old name", "anchor": ""}]


MEMBER = Spoken
