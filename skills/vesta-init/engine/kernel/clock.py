"""The clock. Every date and timestamp the engine writes comes from one of these, so a test can fix it."""
from __future__ import annotations

import datetime


class Clock(object):
    """The system clock."""

    def now(self):
        """The present moment, in UTC."""
        return datetime.datetime.now(datetime.timezone.utc)

    def timestamp(self):
        """UTC, `YYYY-MM-DDTHH:MM:SSZ`."""
        return self.now().strftime("%Y-%m-%dT%H:%M:%SZ")

    def today(self):
        """The local calendar date, `YYYY-MM-DD`."""
        return self.now().astimezone().strftime("%Y-%m-%d")


class FixedClock(Clock):
    """A clock that reads a set moment. `advance` moves it."""

    def __init__(self, moment="2026-01-05T09:00:00Z"):
        self.moment = datetime.datetime.strptime(moment, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)

    def now(self):
        return self.moment

    def today(self):
        return self.moment.strftime("%Y-%m-%d")

    def advance(self, seconds=0, days=0):
        self.moment = self.moment + datetime.timedelta(seconds=seconds, days=days)
