"""`propose <kind> --target <t> [--evidence <id>,…] [--source <s>] [--draft <file>]`: start a proposal."""
from __future__ import annotations

from cli import args
from kernel import frontmatter, ids, yamlsubset
from kernel import tree as trees
from kernel.errors import Refusal, SubsetError, UsageError
from model.abstractions import DISPOSITION, OPEN, OUTCOME, KindError
from model.record import LABEL, UID, Record
from proposals import blocks, proposal as proposals
from session import passes, pending, state
from stores import similar
from stores.filestore import RECORD_DEPTH

INIT = "init"

SECTIONS = (
    ("Why", "the shape the evidence shares, stated without the particular files; two to five sentences"),
    ("Counter-case", "where this would misfire or reach too far, and why it is proposed anyway"),
    ("Cheaper homes considered", "each cheaper way to prevent the shape, with why it falls short; delete this section for a proposal drafted at setup or at a session's close"),
)

# The command builds its change from what it reads, so it runs alone (cli/main.py).
ALONE = True


def _evidence(context, text):
    found = []
    for name in [part.strip() for part in (text or "").split(",") if part.strip()]:
        records, lost = proposals.evidence_records(context, [name])
        if lost:
            raise UsageError("`%s` is not an observation of this project; `--evidence` takes the labels of open observations, separated by commas" % name)
        store, record = records[0]
        if store.type.life(record, DISPOSITION) != OPEN:
            raise UsageError("%s is no longer open (%s), so it cannot be evidence for a new proposal" % (record.label, store.type.life(record, DISPOSITION)))
        found.append(record.ref)
    return list(dict.fromkeys(found))


def _source(context, given):
    if given:
        given = given.strip()
        if not (given == INIT or passes.NUMBERED.match(given) and not given.endswith(".md") or state.ID.match(given)):
            raise UsageError("`--source %s` is none of: a session id, `pass-<n>` as a learn pass names itself, or `%s`" % (given, INIT))
        named = state.read(context.tree, given) if state.ID.match(given) else None
        if named is not None and named.origin is not None:
            raise Refusal(
                "%s reads back an earlier conversation, and reading back writes notes only: what becomes of a note is proposed in a "
                "learn pass, where the owner decides. Nothing was started." % given, "vesta/INTERNALS.md, Earlier conversations")
        return given
    found = state.open_ones(context.tree)
    if len(found) == 1:
        return found[0].id
    raise UsageError("say where the proposal comes from with `--source <session id>`, `--source pass-<n>` or `--source init`; %s" % (
        "no session is open" if not found else "several sessions are open"))


def covered(context, kind, target, draft_text, draft_path):
    """The lines of the note on records that may already cover a draft; empty where none does."""
    try:
        store, replaced = kind.home(target, context)
        front, body, _ = frontmatter.split(draft_text, draft_path)
        fields = yamlsubset.read(front, draft_path, 2, depth=RECORD_DEPTH)
    except (KindError, SubsetError):
        return []
    if store is None:
        return []
    draft = Record(store.name, "", fields, body)
    title, when = store.title(draft), store.type.role(draft, "when")
    if blocks.FILL in str(title) + str(when):
        return []
    found = similar.covering(store, title, when, set(record.uid for record in replaced))
    if not found:
        return []
    lines = ["", "## Possibly already covered by", ""]
    for record in found:
        lines.append("- %s, %s" % (record.label, store.title(record)))
        lines.append("  %s: %s" % (store.type.role_field("when") or "when", " ".join(str(store.type.role(record, "when") or "").split())))
    lines.extend(["", "Shared words are not shared meaning. Either change this proposal to a `latch-edit`, `supersede` or `merge` on the "
                  "record listed, or say in *Counter-case* why the new record is distinct."])
    return lines


def run(context, arguments):
    words, options = args.split(arguments, options=("--target", "--evidence", "--source", "--draft"), takes=True)
    if len(words) != 1 or "--target" not in options:
        raise UsageError("`propose` takes a kind and a target, as `propose add --target <store>`; the kinds are: %s" % (", ".join(context.config.kinds) or "none"))
    kind = proposals.kind_of(context, words[0])
    target = options["--target"].strip()
    try:
        kind.resolve(target, context)
        cost = kind.standing_cost(target, context)
    except KindError as error:
        raise UsageError("`--target %s`: %s" % (target, error))
    store = pending.store_of(context)
    evidence = _evidence(context, options.get("--evidence"))
    source = _source(context, options.get("--source"))
    uid, label = store.next_id("%s %s" % (kind.id, target), proposals.labels_used(context, store))
    fields = {
        UID: uid, LABEL: label, pending.KIND: kind.id, pending.TARGET: target, pending.DRAFTED: context.clock.today(),
        pending.SOURCE: source, pending.EVIDENCE: evidence, pending.SESSIONS: proposals.sessions_of(context, evidence),
        "bar": "", pending.COST: cost, store.type.life_field(OUTCOME): "",
    }
    body = "# %s what would change, in one line>\n" % blocks.FILL
    for name, holds in SECTIONS:
        body += "\n## %s\n%s %s>\n" % (name, blocks.FILL, holds)
    body += "\n## %s\n%s\n" % (proposals.CHANGE, kind.scaffold(target, context, label))
    record = Record(store.name, store.path_for(label), dict((name, value) for name, value in fields.items() if store.type.field(name)), body)
    overlay = trees.Overlay(context.tree)
    overlay.write(record.path, store.text(record))
    draft_path = record.path[:-len(".md")] + proposals.DRAFT
    draft_text = ""
    if kind.draft:
        if "--draft" in options:
            try:
                draft_text = context.tree.read(trees.clean(options["--draft"]))
            except (ValueError, OSError, UnicodeDecodeError):
                raise UsageError("`--draft %s` is not a text file of this project" % options["--draft"])
        else:
            draft_text = kind.draft_text(target, context)
        overlay.write(draft_path, draft_text)
    elif "--draft" in options:
        raise UsageError("a `%s` proposal has no draft" % kind.id)
    overlay.commit()
    context.write("Started %s: %s %s." % (label, kind.id, target))
    context.write()
    context.write("Fill these, replacing every `%s …>` placeholder:" % blocks.FILL)
    context.write("- %s — the title and the sections; how to write one is in %s/SCHEMA.md" % (record.path, store.path))
    if kind.draft:
        context.write("- %s — the full text of the record; leave `%s` and `%s` as `%s`" % (draft_path, UID, LABEL, ids.NEW))
    context.write()
    context.write("Evidence: %d observation%s from %d session%s. Standing cost: %s." % (
        len(evidence), "" if len(evidence) == 1 else "s", fields[pending.SESSIONS], "" if fields[pending.SESSIONS] == 1 else "s", cost))
    context.write("Then run `proposals %s`: it says what is still wrong with the files and which records may already cover it." % label)
    for line in covered(context, kind, target, draft_text, draft_path) if kind.draft else []:
        context.write(line)
    return 0
