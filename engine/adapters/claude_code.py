"""The `claude-code` history: the conversations Claude Code keeps for a project, one file each.

The form of these files is not documented. What is read here is what they held when this was
written; a line that does not read is counted, and a file that reads as nothing is refused.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re

from model.abstractions import Conversation, History, HistoryError, Turn

HOME = "CLAUDE_CONFIG_DIR"
ENDING = ".jsonl"
OWNER, AGENT, QUEUED = "user", "assistant", "attachment"
SKIPPED = ("isSidechain", "isMeta", "isCompactSummary")
HUMAN = "human"
# What the harness writes in the owner's place: its own tags, and the sentences it opens with.
TAGS = re.compile(
    r"\s*<(command-name|command-message|command-args|local-command-[a-z]+|task-notification|system-reminder|"
    r"bash-input|bash-stdout|bash-stderr|scheduled-task|user-prompt-submit-hook|side-sessions-event|"
    r"cross-session-message|agent-message|create-pr-command|ci-monitor-event)[ >]"
)
# A message that is one block of the harness's own kind of tag and nothing after it.
BLOCK = re.compile(r"\s*<([a-z]+(?:-[a-z]+)+)(?: [^>]*)?>.*</\1>\s*\Z", re.S)
OPENINGS = (
    "[Request interrupted by user",
    "Caveat: The messages below were generated",
    "This session is being continued from a previous conversation",
    "Stop hook feedback:",
)
# The owner's words where they turned an action down and said why.
TURNED_DOWN = re.compile(r"\s*The user doesn't want to proceed with this tool use\..*?the user said:\s*", re.S)
# What the harness puts inside the owner's own message, which is taken out and the rest kept.
REMINDER = re.compile(r"<(system-reminder|artifact-view-context)(?: [^>]*)?>.*?</\1>\s*", re.S)
# A command the owner typed with words after it: the words are the owner's.
COMMAND = re.compile(r"\s*(?:<command-message>.*?</command-message>\s*)?<command-name>\s*(.*?)\s*</command-name>", re.S)
ARGUMENTS = re.compile(r"<command-args>\s*(.*?)\s*</command-args>", re.S)


def _blocks(content):
    return [block for block in content if isinstance(block, dict)] if isinstance(content, list) else []


def _words(content):
    """The words of one message: its text where it is text, the text blocks where it is a list."""
    if isinstance(content, str):
        return content
    return "\n".join(block["text"] for block in _blocks(content) if block.get("type") == "text" and isinstance(block.get("text"), str))


def _typed(text):
    """What the owner typed in a message, less what the harness put into it: a command's words where
    the message is a command, else the text without the harness's own blocks."""
    command, arguments = COMMAND.match(text), ARGUMENTS.search(text)
    if command:
        # A command typed alone says nothing to keep, and is not the harness's either.
        return "%s %s" % (command.group(1), arguments.group(1)) if arguments and arguments.group(1) else ""
    return REMINDER.sub("", text).strip()


def _answers(entry):
    """What the owner chose where the agent put a question to them: one text for each question."""
    result = entry.get("toolUseResult")
    answers = result.get("answers") if isinstance(result, dict) else None
    if not isinstance(answers, dict):
        return []
    found = []
    for question, answer in answers.items():
        if isinstance(answer, list):
            answer = ", ".join(part for part in answer if isinstance(part, str))
        if isinstance(question, str) and isinstance(answer, str) and answer.strip():
            found.append("The agent asked: %s\nThe owner answered: %s" % (" ".join(question.split()), answer.strip()))
    return found


def _refusals(content):
    """What the owner said on turning an action down, for each result block that carries such words."""
    found = []
    for block in _blocks(content):
        if block.get("type") != "tool_result" or block.get("is_error") is not True:
            continue
        text = _words(block.get("content"))
        said = TURNED_DOWN.match(text)
        if said and text[said.end():].strip():
            found.append(text[said.end():].strip())
    return found


def _harness(text):
    return bool(TAGS.match(text)) or bool(BLOCK.match(text)) or text.lstrip().startswith(OPENINGS)


def _kind(holder):
    """`human`, another kind, or None where the entry does not say who it came from."""
    origin = holder.get("origin")
    return origin.get("kind") if isinstance(origin, dict) and isinstance(origin.get("kind"), str) else None


class ClaudeCode(History):
    id = "claude-code"
    name = "Claude Code"
    residue = ("only conversations started in the project's own folder; one started in another folder is kept under that folder's "
               "name, and is read by naming that folder or file with `--in <path>`")
    takes_path = True

    def _home(self):
        return os.path.abspath(os.environ.get(HOME) or os.path.join(os.path.expanduser("~"), ".claude"))

    def places(self):
        """The folder for this project, under each form of the root's path the harness may have used;
        or the folder or file the owner named."""
        if self.given:
            given = os.path.expanduser(self.given)
            return [os.path.abspath(given if os.path.isabs(given) else os.path.join(self.root, given))]
        forms = dict.fromkeys((os.path.abspath(self.root), os.path.realpath(self.root)))
        return [os.path.join(self._home(), "projects", re.sub(r"[^A-Za-z0-9]", "-", form)) for form in forms]

    def conversations(self):
        places = self.places()
        if self.given and os.path.isfile(places[0]) and not os.path.islink(places[0]):
            if not places[0].endswith(ENDING):
                raise HistoryError("%s is no `%s` file; saved text is read by the place `file`" % (places[0], ENDING))
            leaf, moment = os.path.basename(places[0]), os.path.getmtime(places[0])
            return [Conversation(leaf[:-len(ENDING)], datetime.datetime.fromtimestamp(moment).strftime("%Y-%m-%d"), places[0])]
        folders = [folder for folder in places if os.path.isdir(folder)]
        if not folders:
            raise HistoryError("there is no folder %s" % " or ".join(places))
        found, links = {}, 0
        for folder in folders:
            try:
                for leaf in os.listdir(folder):
                    path = os.path.join(folder, leaf)
                    if not leaf.endswith(ENDING):
                        continue
                    if os.path.islink(path) or not os.path.isfile(path):
                        links += 1
                        continue
                    moment = os.path.getmtime(path)
                    day = datetime.datetime.fromtimestamp(moment).strftime("%Y-%m-%d")
                    found.setdefault(leaf[:-len(ENDING)], (moment, Conversation(leaf[:-len(ENDING)], day, path)))
            except OSError as error:
                raise HistoryError("%s cannot be listed (%s)" % (folder, error))
        self.left_out = "%d that %s a link or no file" % (links, "is" if links == 1 else "are") if links else ""
        if self.given and not found:
            raise HistoryError("%s holds no `%s` file" % (folders[0], ENDING))
        return [conversation for _, conversation in sorted(found.values(), key=lambda pair: (pair[0], pair[1].ref))]

    def _entry(self, entry, unnamed):
        """([what was said in one line of the file], how many things in it were the harness's).
        `unnamed` gives the mark of an entry that carries no id of its own."""
        kind = entry.get("type")
        mark = entry.get("uuid") if isinstance(entry.get("uuid"), str) and entry.get("uuid") else unnamed(entry)
        at = entry.get("timestamp") if isinstance(entry.get("timestamp"), str) else ""
        if any(entry.get(key) is True for key in SKIPPED):
            return [], 0
        if kind == QUEUED:
            # What the owner typed while the agent was working.
            held = entry.get("attachment")
            if not isinstance(held, dict) or held.get("type") != "queued_command" or held.get("commandMode") != "prompt":
                return [], 0
            text = _typed(held.get("prompt")) if isinstance(held.get("prompt"), str) else ""
            if not text.strip() or held.get("isMeta") is True:
                return [], 0
            if _kind(held) not in (None, HUMAN) or _harness(text):
                return [], 1
            return [Turn(Turn.OWNER, text, at, mark)], 0
        message = entry.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if kind == AGENT:
            text = _words(content)
            return ([Turn(Turn.AGENT, text, at, mark)] if text.strip() else []), 0
        if kind != OWNER:
            return [], 0
        inside = _refusals(content) or _answers(entry)
        if inside:
            return [Turn(Turn.OWNER, text, at, "%s:%d" % (mark, number) if mark else "") for number, text in enumerate(inside)], 0
        if any(block.get("type") == "tool_result" for block in _blocks(content)):
            return [], 0
        text = _typed(_words(content))
        if not text.strip():
            return [], 0
        if _kind(entry) not in (None, HUMAN) or _harness(text):
            return [], 1
        return [Turn(Turn.OWNER, text, at, mark)], 0

    def turns(self, conversation):
        found, unread, lines, harness, known, seen = [], 0, 0, 0, 0, {}

        def unnamed(entry):
            # Known by its conversation, its words, and which time these words occur in it.
            words = json.dumps(entry.get("message") or entry.get("attachment"), sort_keys=True, default=str)
            seen[words] = seen.get(words, 0) + 1
            return hashlib.sha256(("%s\n%d\n%s" % (conversation.ref, seen[words], words)).encode("utf-8", "replace")).hexdigest()[:16]

        try:
            with open(conversation.path, "rb") as handle:
                for raw in handle:
                    if not raw.strip():
                        continue
                    lines += 1
                    try:
                        entry = json.loads(raw.decode("utf-8"))
                    except (ValueError, UnicodeDecodeError, RecursionError):
                        unread += 1
                        continue
                    if not isinstance(entry, dict):
                        unread += 1
                        continue
                    known += entry.get("type") in (OWNER, AGENT)
                    turns, left = self._entry(entry, unnamed)
                    found.extend(turns)
                    harness += left
        except OSError as error:
            raise HistoryError("%s cannot be read (%s)" % (conversation.path, error))
        if lines and unread == lines:
            raise HistoryError("%s does not read as a Claude Code conversation: none of its %d lines is an entry" % (conversation.path, lines))
        if lines and not known:
            raise HistoryError(
                "%s does not read as a Claude Code conversation: none of its %d lines is something said, in the form this engine knows. "
                "Where another harness wrote it, or a later Claude Code, save the conversation as text and read it with the place `file`"
                % (conversation.path, lines))
        if unread and not found:
            raise HistoryError("%s holds nothing that reads as something said, and %d of its %d lines do not read" % (conversation.path, unread, lines))
        self.unread, self.harness = unread, harness
        return found


MEMBER = ClaudeCode
