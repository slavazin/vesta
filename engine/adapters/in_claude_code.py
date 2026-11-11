"""The `claude-code` harness: what a command can tell where Claude Code started it.

Read from the environment, as Claude Code documents it. Nothing here opens a file.
"""
from __future__ import annotations

import json
import re

from model.abstractions import Harness

RUNNING, CONVERSATION = "CLAUDECODE", "CLAUDE_CODE_SESSION_ID"
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")
PROGRAM = "claude"
FILE = ".claude/settings.local.json"
EVENT = "UserPromptSubmit"
READING = ("Read", "Grep", "Glob")


class InClaudeCode(Harness):
    id = "claude-code"
    name = "Claude Code"
    residue = "a copy of a conversation is started with the `claude` program, which has to be found on the path"
    history = "claude-code"
    forks = True

    def here(self):
        return self.environ.get(RUNNING) == "1"

    def conversation(self):
        name = self.environ.get(self.ORIGINAL) or self.environ.get(CONVERSATION) or ""
        return name if NAME.match(name) else ""

    def fork(self, conversation, prompt, allowed, reads=False):
        # The copy keeps no file of its own and runs none of the project's hooks, so it starts no copy in turn.
        command = [PROGRAM, "-p", "--resume", conversation, "--fork-session", "--no-session-persistence",
                   "--settings", json.dumps({"disableAllHooks": True})]
        rules = ["Bash(%s *)" % opening for opening in allowed] + (list(READING) if reads else [])
        if rules:
            command.extend(["--allowedTools"] + rules)
        return command + ["--", prompt]

    def hook(self, command):
        entry = {"hooks": {EVENT: [{"hooks": [{"type": "command", "command": command, "async": True}]}]}}
        return FILE, json.dumps(entry, indent=2)

    def said(self, sent):
        name, words = sent.get("session_id"), sent.get("prompt")
        return (name if isinstance(name, str) and NAME.match(name) else ""), (words if isinstance(words, str) else "")


    def adopt(self, sent):
        name = self.said(sent)[0] if isinstance(sent, dict) else ""
        if not name or sent.get("hook_event_name") != EVENT:
            return None
        return dict(self.environ, **{RUNNING: "1", CONVERSATION: name})


MEMBER = InClaudeCode
