"""The schema-block reader: builds a record type from the `vesta-schema` block of a store's SCHEMA.md."""
from __future__ import annotations

import datetime
import re

from kernel import ids, markdown, yamlsubset
from kernel.errors import SubsetError
from kernel.finding import ERROR
from model.abstractions import (
    APPROVED_BY, DECIDED, DISPOSITION, LIFECYCLE, OUTCOME, RETIRED_BECAUSE, ROLES, STATUS, SUPERSEDED_BY, SUPERSEDES, RecordType,
)
from model.record import LABEL, UID, Problem

TAG = "vesta-schema"
FILE = "SCHEMA.md"
TYPES = ("text", "integer", "date", "enum", "ref", "refs", "list", "triggers")
LAYOUTS = ("flat", "open-archive")
KEYS = ("layout", "title", "fields", "sections", "index", "lifecycle", "payload-section", "conditions")
FIELD_KEYS = ("name", "type", "values", "patterns", "required", "required-when", "mutable")
TRIGGER_KEYS = ("id", "if", "then", "probe", "resolved")
THEN = ("apply", "re-decide", "re-derive", "check", "retire")
THEN_OTHER = re.compile(r"other\(.+\)")
TRIGGER_ID = re.compile(r"t[0-9]+\Z")
DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
WHEN = re.compile(r"(?P<field>[a-z][a-z0-9-]*) in (?P<values>.+)\Z")


class Field(object):
    """One field of a record type."""

    def __init__(self, item):
        self.name = item.get("name", "")
        self.type = item.get("type", "text")
        self.values = [str(value) for value in item.get("values", [])] if isinstance(item.get("values"), list) else []
        self.patterns = [str(value) for value in item.get("patterns", [])] if isinstance(item.get("patterns"), list) else []
        self.required = item.get("required") is True
        self.mutable = item.get("mutable") is True
        self.when_field = None
        self.when_values = []
        match = WHEN.match(item.get("required-when", "")) if isinstance(item.get("required-when"), str) else None
        if match:
            self.when_field = match.group("field")
            self.when_values = [value.strip() for value in match.group("values").split(",") if value.strip()]

    def empty(self):
        """What the field holds when it holds nothing."""
        if self.type in ("refs", "list", "triggers"):
            return []
        return 0 if self.type == "integer" else ""


def _is_empty(value):
    return value is None or value == [] or (isinstance(value, str) and value.strip() == "")


def _kind(value):
    """What a value read from frontmatter is, in plain words."""
    if isinstance(value, bool):
        return "true or false"
    if isinstance(value, int):
        return "a number"
    if isinstance(value, list):
        return "a list"
    if isinstance(value, dict):
        return "a mapping"
    return "text"


def _is_date(value):
    if not isinstance(value, str) or not DATE.match(value):
        return False
    try:
        datetime.datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


class SchemaRecordType(RecordType):
    """A record type as its schema block states it."""

    def __init__(self, data):
        self.layout = data.get("layout", "flat")
        self.title_required = data.get("title", "required") == "required"
        self.fields = [Field(item) for item in data.get("fields", []) if isinstance(item, dict)]
        self.sections = [
            (item.get("name", ""), item.get("required") is True)
            for item in data.get("sections", []) if isinstance(item, dict)
        ]
        self.roles = dict(data.get("index", {})) if isinstance(data.get("index"), dict) else {}
        self.lifecycle = dict(data.get("lifecycle", {})) if isinstance(data.get("lifecycle"), dict) else {}
        self.payload_section = data.get("payload-section", "") if isinstance(data.get("payload-section"), str) else ""
        self.conditions = []
        for item in data.get("conditions", []):
            name, _, argument = item.partition(":")
            self.conditions.append((name, argument))
        self._by_name = dict((field.name, field) for field in self.fields)

    def field(self, name):
        return self._by_name.get(name)

    # ------------------------------------------------------------------------------------ validation

    def validate(self, record):
        found = []

        def problem(name, message):
            line = yamlsubset.line_of(record.front, (name,), 2) if name else record.body_line
            found.append(Problem(ERROR, line, message))

        for name in record.fields:
            if name not in self._by_name:
                problem(name, "the key `%s` is not a field of this store" % name)
        for field in self.fields:
            if field.name not in record.fields:
                if field.required:
                    problem("", "the field `%s` is missing from the frontmatter" % field.name)
                    continue
            value = record.fields.get(field.name, field.empty())
            if field.type in ("refs", "list") and value == "":
                value = []
            message = self._type_problem(field, value)
            if message:
                problem(field.name, message)
                continue
            if field.required and _is_empty(value):
                problem(field.name, "the field `%s` is empty" % field.name)
            elif field.when_field is not None:
                holds = record.fields.get(field.when_field) in field.when_values
                said = "`%s` is %s" % (field.when_field, " or ".join("`%s`" % v for v in field.when_values))
                if holds and _is_empty(value):
                    problem(field.name, "the field `%s` is empty; it is required when %s" % (field.name, said))
                elif not holds and not _is_empty(value):
                    problem(field.name, "the field `%s` is filled; it is filled only when %s" % (field.name, said))
        if UID in self._by_name and record.uid and not ids.UID.match(record.uid):
            problem(UID, "the field `%s` is eight hexadecimal characters" % UID)
        if LABEL in self._by_name and record.label:
            name = record.path.rsplit("/", 1)[-1]
            if name != record.label + ".md":
                problem(LABEL, "the field `%s` is `%s` and the file is named `%s`; the file must be named `%s.md`" % (LABEL, record.label, name, record.label))
        found.extend(self._body_problems(record))
        return found

    def _type_problem(self, field, value):
        name, kind = field.name, field.type
        if kind in ("text", "ref", "date", "enum"):
            if not isinstance(value, str):
                hint = "; put it in double quotes" if isinstance(value, (int, bool)) else ""
                return "the field `%s` holds %s; it must be one line of text%s" % (name, _kind(value), hint)
            if value == "":
                return None
            if kind == "date" and not _is_date(value):
                return "the field `%s` is `%s`; it must be a date written YYYY-MM-DD" % (name, value)
            if kind == "enum" and value not in field.values and not any(re.fullmatch(p, value) for p in field.patterns):
                forms = ["`%s`" % v for v in field.values] + ["the form `%s`" % p for p in field.patterns]
                return "the field `%s` is `%s`; it must be one of %s" % (name, value, ", ".join(forms))
            if kind == "ref" and not ids.REF.match(value):
                return "the field `%s` is `%s`; a record is named `<label>@<internal id>`, as `D-003@7f3a9c2e`" % (name, value)
            return None
        if kind == "integer":
            if not isinstance(value, int) or isinstance(value, bool):
                return "the field `%s` holds %s; it must be a whole number" % (name, _kind(value))
            return None
        if kind in ("refs", "list"):
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                return "the field `%s` holds %s; it must be a list of text" % (name, _kind(value))
            if any(item.strip() == "" for item in value):
                return "the field `%s` has an empty item" % name
            if kind == "refs":
                for item in value:
                    if not ids.REF.match(item):
                        return "the field `%s` has the item `%s`; a record is named `<label>@<internal id>`, as `D-003@7f3a9c2e`" % (name, item)
            return None
        if kind == "triggers":
            return self._triggers_problem(name, value)
        return None

    def _triggers_problem(self, name, value):
        if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
            return "the field `%s` holds %s; it must be a list of triggers, each with `id`, `if`, `then`, `probe` and `resolved`" % (name, _kind(value))
        seen = set()
        for item in value:
            label = item.get("id")
            if not isinstance(label, str) or not TRIGGER_ID.match(label):
                return "a trigger of `%s` has the id `%s`; trigger ids are `t1`, `t2`, …" % (name, label)
            if label in seen:
                return "the trigger id `%s` occurs twice in `%s`" % (label, name)
            seen.add(label)
            for key in item:
                if key not in TRIGGER_KEYS:
                    return "the trigger `%s` has the key `%s`; a trigger has `id`, `if`, `then`, `probe` and `resolved`" % (label, key)
            for key in TRIGGER_KEYS[1:]:
                if not isinstance(item.get(key, ""), str):
                    return "`%s` of the trigger `%s` is text" % (key, label)
            if not item.get("if"):
                return "the trigger `%s` has no `if`" % label
            then = item.get("then", "")
            first = then.split(" ", 1)[0] if then else ""
            if first not in THEN and not THEN_OTHER.match(then):
                return "`then` of the trigger `%s` opens with one of %s, or `other(<what>)`" % (label, ", ".join("`%s`" % t for t in THEN))
        return None

    def _body_problems(self, record):
        found = []
        document = markdown.Document(record.body)
        first = next((line for line in document.lines if line.strip()), "")
        if self.title_required:
            if not first.startswith("# ") or not first[2:].strip():
                found.append(Problem(ERROR, record.body_line, "the body opens with one `# ` title line"))
        elif first.startswith("# "):
            found.append(Problem(ERROR, record.body_line, "a record of this store has no title line"))
        fenced = markdown.fenced_lines(document.lines)
        titles = [index for index, line in enumerate(document.lines) if line.startswith("# ") and index not in fenced]
        if len(titles) > 1:
            found.append(Problem(ERROR, record.body_line + titles[1], "the body has a second `# ` title line; a record has one"))
        if not self.sections:
            return found
        listed = [name for name, _ in self.sections]
        present = document.names()
        for name, required in self.sections:
            if required and name not in present:
                found.append(Problem(ERROR, record.body_line, "the section `## %s` is missing" % name))
        position = -1
        seen = set()
        for section in document.sections:
            line = record.body_line + section.heading
            if section.name not in listed:
                found.append(Problem(ERROR, line, "the section `## %s` is not a section of this store; it has %s" % (section.name, ", ".join(listed))))
            elif section.name in seen:
                found.append(Problem(ERROR, line, "the section `## %s` occurs twice" % section.name))
            elif listed.index(section.name) < position:
                found.append(Problem(ERROR, line, "the section `## %s` is out of order; the order is %s" % (section.name, ", ".join(listed))))
            else:
                position = listed.index(section.name)
            seen.add(section.name)
        return found

    # --------------------------------------------------------------------------------------- writing

    def front(self, record):
        out = {}
        for field in self.fields:
            value = record.fields.get(field.name, field.empty())
            if field.type in ("refs", "list") and value == "":
                value = []
            if field.type == "triggers" and isinstance(value, list):
                value = [
                    dict((key, item.get(key, "")) for key in TRIGGER_KEYS) if isinstance(item, dict) else item
                    for item in value
                ]
            out[field.name] = value
        return out


LIFE_TYPES = {
    STATUS: ("enum", "text"), SUPERSEDES: ("refs",), SUPERSEDED_BY: ("ref",), RETIRED_BECAUSE: ("text",), DISPOSITION: ("text",),
    DECIDED: ("date",), APPROVED_BY: ("text",), OUTCOME: ("text",),
}
ROLE_TYPES = {"when": ("text",), "why": ("text",), "except": ("text",), "paths": ("list",), "triggers": ("triggers",)}


def _show(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "nothing"
    if isinstance(value, (list, dict)):
        return "a list" if isinstance(value, list) else "a mapping"
    return "`%s`" % value


def _block_problems(data):
    found = []
    for key in data:
        if key not in KEYS:
            found.append("the schema block has the key `%s`; its keys are %s" % (key, ", ".join(KEYS)))
    if data.get("layout") not in LAYOUTS:
        found.append("`layout` is %s; it must be one of %s" % (_show(data.get("layout")), ", ".join(LAYOUTS)))
    if data.get("title") not in ("required", "none"):
        found.append("`title` is %s; it must be `required` or `none`" % _show(data.get("title")))
    fields = data.get("fields")
    if not isinstance(fields, list) or not fields or not all(isinstance(item, dict) for item in fields):
        found.append("`fields` must be a list of fields, each with `name` and `type`")
        fields = []
    names = {}
    for item in fields:
        name = item.get("name")
        if not isinstance(name, str) or not name:
            found.append("a field has no `name`")
            continue
        if name in names:
            found.append("the field `%s` is listed twice" % name)
        names[name] = item.get("type")
        for key in item:
            if key not in FIELD_KEYS:
                found.append("the field `%s` has the key `%s`; a field has %s" % (name, key, ", ".join(FIELD_KEYS)))
        if item.get("type") not in TYPES:
            found.append("the field `%s` has the type %s; the types are %s" % (name, _show(item.get("type")), ", ".join(TYPES)))
        for key in ("required", "mutable"):
            if key in item and not isinstance(item[key], bool):
                found.append("`%s` of the field `%s` is %s; it must be `true` or `false`" % (key, name, _show(item[key])))
        for key in ("values", "patterns"):
            if key in item and not (isinstance(item[key], list) and all(isinstance(value, str) and value for value in item[key])):
                found.append("`%s` of the field `%s` must be a list of text" % (key, name))
        if item.get("type") == "enum" and not item.get("values") and not item.get("patterns"):
            found.append("the field `%s` is an enum with no `values` and no `patterns`" % name)
        for pattern in item.get("patterns", []) if isinstance(item.get("patterns"), list) else []:
            try:
                re.compile(str(pattern))
            except re.error:
                found.append("the field `%s` has a pattern that is not a regular expression: `%s`" % (name, pattern))
    for item in fields:
        name, when = item.get("name"), item.get("required-when")
        if when is None or not isinstance(name, str):
            continue
        match = WHEN.match(when) if isinstance(when, str) else None
        if not match or not [value for value in match.group("values").split(",") if value.strip()]:
            found.append("`required-when` of the field `%s` must have the form `<field> in <value>, <value>`" % name)
        elif match.group("field") not in names:
            found.append("`required-when` of the field `%s` names `%s`, which is not a field" % (name, match.group("field")))
    for required in (UID, LABEL):
        if fields and required not in names:
            found.append("every record type has the field `%s`" % required)
    sections = data.get("sections", [])
    if not isinstance(sections, list) or not all(isinstance(item, dict) and isinstance(item.get("name"), str) for item in sections):
        found.append("`sections` must be a list of sections, each with `name` and `required`")
        sections = []
    section_names = [item.get("name") for item in sections]
    for name in sorted(set(section_names)):
        if section_names.count(name) > 1:
            found.append("the section `%s` is listed twice" % name)
    for item in sections:
        if "required" in item and not isinstance(item["required"], bool):
            found.append("`required` of the section `%s` is %s; it must be `true` or `false`" % (item.get("name"), _show(item["required"])))
    index = data.get("index", {})
    if not isinstance(index, dict):
        found.append("`index` must be a mapping of index roles to field names")
        index = {}
    for role, name in index.items():
        if role not in ROLES:
            found.append("`%s` is not an index role; the roles are %s" % (role, ", ".join(ROLES)))
        elif name not in names:
            found.append("the index role `%s` names %s, which is not a field" % (role, _show(name)))
        elif names[name] not in ROLE_TYPES[role]:
            found.append("the index role `%s` names `%s`, whose type is `%s`; that role takes a field of type `%s`" % (role, name, names[name], ROLE_TYPES[role][0]))
    lifecycle = data.get("lifecycle", {})
    if not isinstance(lifecycle, dict):
        found.append("`lifecycle` must be a mapping of lifecycle roles to field names")
        lifecycle = {}
    for role, name in lifecycle.items():
        if role not in LIFECYCLE:
            found.append("`%s` is not a lifecycle role; the roles are %s" % (role, ", ".join(LIFECYCLE)))
        elif name not in names:
            found.append("the lifecycle role `%s` names %s, which is not a field" % (role, _show(name)))
        elif names[name] not in LIFE_TYPES[role]:
            found.append("the lifecycle role `%s` names `%s`, whose type is `%s`; that role takes a field of type `%s`" % (role, name, names[name], LIFE_TYPES[role][0]))
    payload = data.get("payload-section")
    if payload is not None and payload not in section_names:
        found.append("`payload-section` names %s, which is not a section" % _show(payload))
    conditions = data.get("conditions", [])
    if not isinstance(conditions, list) or not all(isinstance(item, str) for item in conditions):
        found.append("`conditions` must be a list of condition names")
    return found


def read(text, file=FILE):
    """Build the record type from a SCHEMA.md text.

    Returns (record type or None, [(line, message)]). The type is None where the file has no single
    readable block.
    """
    blocks = markdown.fenced_blocks(text, TAG)
    unclosed = markdown.unclosed_fence(text)
    if unclosed is not None:
        return None, [(unclosed, "the fenced block opened on this line is never closed")]
    if len(blocks) != 1:
        return None, [(1, "the file holds %d `%s` blocks; it must hold exactly one" % (len(blocks), TAG))]
    _, content, line = blocks[0]
    try:
        data = yamlsubset.read(content, file, line + 1)
    except SubsetError as error:
        return None, [(error.line, error.message)]
    found = _block_problems(data)
    if found:
        return None, [(line, message) for message in found]
    return SchemaRecordType(data), []


def has_role(record_type, role):
    return record_type.role_field(role) is not None
