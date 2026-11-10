"""The `config` check."""
from __future__ import annotations

from kernel.finding import ERROR, Finding
from model import config
from model.abstractions import Check


class ConfigCheck(Check):
    id = "config"
    residue = "not whether the configuration suits the project"

    def run(self, context):
        return [
            Finding(ERROR, self.id, config.PATH, line, message)
            for line, message in config.problems(context.config_text, context.known)
        ]


MEMBER = ConfigCheck
