"""The `file` history: a conversation the owner saved as text, or a folder of them, at a path they name."""
from __future__ import annotations

import datetime
import os

import hashlib

from model.abstractions import Conversation, History, HistoryError, Turn

MOST = 200


class Files(History):
    id = "file"
    name = "saved text"
    residue = "who said what: the text is read as it stands, and the reader tells the owner's words from the agent's"
    takes_path = True
    needs_path = True
    day_word = "File last changed on"
    OTHERS = ".jsonl"

    def places(self):
        given = os.path.expanduser(self.given)
        return [os.path.abspath(given if os.path.isabs(given) else os.path.join(self.root, given))] if self.given else []

    def _one(self, path):
        moment = os.path.getmtime(path)
        return moment, Conversation(os.path.basename(path), datetime.datetime.fromtimestamp(moment).strftime("%Y-%m-%d"), path)

    def conversations(self):
        if not self.places():
            raise HistoryError("no path was given")
        place = self.places()[0]
        found, passed = [], {"link": 0, "folder": 0, "hidden file": 0, "`.jsonl` file": 0}
        try:
            if os.path.isfile(place):
                return [self._one(place)[1]]
            if not os.path.isdir(place):
                raise HistoryError("there is no file or folder %s" % place)
            for leaf in os.listdir(place):
                path = os.path.join(place, leaf)
                if os.path.islink(path):
                    passed["link"] += 1
                elif os.path.isdir(path):
                    passed["folder"] += 1
                elif leaf.startswith("."):
                    passed["hidden file"] += 1
                elif leaf.endswith(self.OTHERS):
                    passed["`.jsonl` file"] += 1
                elif os.path.isfile(path):
                    found.append(self._one(path))
        except OSError as error:
            raise HistoryError("%s cannot be listed (%s)" % (place, error))
        if len(found) > MOST:
            raise HistoryError("%s holds %d files; the most this reads from one folder is %d. Name a smaller folder, or one file" % (place, len(found), MOST))
        self.left_out = ", ".join("%d %s%s" % (count, what, "" if count == 1 else "s") for what, count in passed.items() if count)
        if passed["`.jsonl` file"]:
            self.left_out += " (the place `claude-code` reads `.jsonl` files that Claude Code wrote; one named alone is read here as text)"
        return [conversation for _, conversation in sorted(found, key=lambda pair: (pair[0], pair[1].ref))]

    def turns(self, conversation):
        try:
            with open(conversation.path, "rb") as handle:
                raw = handle.read()
        except OSError as error:
            raise HistoryError("%s cannot be read (%s)" % (conversation.path, error))
        if b"\x00" in raw:
            raise HistoryError("%s is not UTF-8 text; a file saved as UTF-16, or one that is not text, reads this way" % conversation.path)
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise HistoryError("%s is not UTF-8 text" % conversation.path)
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        self.unread = self.harness = 0
        # A paragraph is known by its file, its words, and which time those words occur in the file:
        # the same words in another file are another thing said, and a paragraph put in above leaves
        # the ones below it known.
        found, seen = [], {}
        place = os.path.normcase(os.path.realpath(conversation.path))
        for paragraph in text.split("\n\n"):
            if paragraph.strip():
                words = paragraph.strip("\n")
                seen[words] = seen.get(words, 0) + 1
                mark = hashlib.sha256(("%s\n%d\n%s" % (place, seen[words], words)).encode("utf-8", "replace")).hexdigest()[:16]
                found.append(Turn(Turn.UNKNOWN, words, "", mark))
        return found


MEMBER = Files
