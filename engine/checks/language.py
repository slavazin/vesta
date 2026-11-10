"""The `language` check: phrases that mark a sentence written from inside a session."""
from __future__ import annotations

import re

from kernel import markdown, yamlsubset
from kernel.finding import ERROR, WARNING, Finding
from model.abstractions import Check

FILE = "vesta/language.md"
HEADING = "### Tells"
ROLES = ("when", "why")
CODE = re.compile(r"`[^`]*`")
RECORD_ID = re.compile(r"\b[A-Za-z]+-[0-9]+(?:-[0-9a-f]{8})?(?:@[0-9a-f]{8})?\b")


def tells(text):
    """The phrases of the Tells table of the writing rules: the first column, split at commas."""
    lines = markdown.lines_of(text)
    for index, line in enumerate(lines):
        if line.strip() == HEADING:
            table = markdown.read_table("\n".join(lines[index + 1:]))
            if table is None:
                return []
            found = []
            for row in table.rows:
                found.extend(phrase.strip() for phrase in row[0].split(",") if phrase.strip())
            return found
    return []


def found_in(text, phrases):
    """The phrases that occur in a text as whole words, without regard to case; text in backticks
    and record ids are not read."""
    text = RECORD_ID.sub(" ", CODE.sub(" ", text))
    hits = []
    for phrase in phrases:
        pattern = r"(?<!\w)" + r"\s+".join(re.escape(word) for word in phrase.split()) + r"(?!\w)"
        if re.search(pattern, text, re.IGNORECASE):
            hits.append(phrase)
    return hits


class LanguageCheck(Check):
    id = "language"
    residue = "words only: not whether a sentence is true, falsifiable or clear; English tells only"

    def run(self, context):
        if not context.tree.is_file(FILE):
            return [Finding(ERROR, self.id, FILE, 1, "the writing rules file is missing, so no record was read for tells")]
        phrases = tells(context.tree.read(FILE))
        if not phrases:
            return [Finding(ERROR, self.id, FILE, 1, "no table of phrases was found under `%s`, so no record was read for tells" % HEADING)]
        found = []
        for store in context.stores.all():
            if not store.settings.governed:
                continue
            for record in store.list():
                document = markdown.Document(record.body)
                places = []
                if document.title:
                    places.append(("the title", record.body_line + document.title_index, document.title))
                for role in ROLES:
                    name = store.type.role_field(role)
                    if name and isinstance(record.get(name), str):
                        places.append(("the `%s` line" % name, yamlsubset.line_of(record.front, (name,), 2), record.get(name)))
                section = document.section(store.type.payload_section) if store.type.payload_section else None
                if section is not None:
                    places.append(("the %s section" % section.name, record.body_line + section.heading, document.text_of(section)))
                for where, line, text in places:
                    for phrase in found_in(text, phrases):
                        found.append(Finding(
                            WARNING, self.id, record.path, line,
                            "%s holds \"%s\", which reads as written from inside a session; %s says what to write instead" % (where, phrase, FILE),
                        ))
        return found


MEMBER = LanguageCheck
