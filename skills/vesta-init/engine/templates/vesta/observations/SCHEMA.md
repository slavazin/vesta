# How to write an observation

An observation is one file under `open/`: a frontmatter block, a title, and a few lines. It records one
thing a session noticed, with one anchor a reader can open. A session writes observations at its close
through `obs add` and never reads earlier ones. The engine fills `uid`, `id`, `date`, `session`,
`disposition` and `held`.

## Schema

The engine validates every observation against this block. The block changes through a `schema` proposal.

```vesta-schema
layout: open-archive
title: required
conditions: ["body-max:600", "no-labels:Fix:,Proposal:,TODO:", archive-agrees]
fields:
  - name: uid
    type: text
    required: true
  - name: id
    type: text
    required: true
  - name: date
    type: date
    required: true
  - name: session
    type: text
    required: true
  - name: via
    type: enum
    values: [owner-steer, should-have-loaded, off-map, trigger-fired, contradiction, jot]
    patterns:
      - lens:[a-z0-9-]+
      - row:[a-z0-9-]+
      - other\(.+\)
    required: true
  - name: anchor
    type: text
    required: true
  - name: record
    type: ref
    required-when: via in should-have-loaded, trigger-fired, contradiction
  - name: recheck
    type: text
  - name: steer-kind
    type: enum
    values: [correction, direction, choice, preference]
    patterns:
      - other\(.+\)
    required-when: via in owner-steer
  - name: moment
    type: enum
    values: [start, work, close]
    required-when: via in owner-steer
  - name: missed-by
    type: text
    required-when: via in owner-steer, should-have-loaded
  - name: disposition
    type: text
    required: true
    mutable: true
  - name: held
    type: list
    mutable: true
sections: []
```

In the block, `required` marks a field that may not be empty, and `required-when` one that is filled
exactly when another field holds a named value. A field marked `mutable` may change after the record is
written; every other field is fixed once written.

## Fields

| Field | Holds |
|---|---|
| `uid`, `id`, `date`, `session` | written by the engine |
| `via` | where the noticing came from: `owner-steer`, `should-have-loaded`, `off-map`, `trigger-fired`, `contradiction`, `jot`, `lens:<name>`, `row:<id>`, or `other(<what>)` |
| `anchor` | one thing a reader can open: a path, a commit, a record label, a link, or `owner, YYYY-MM-DD`. A conversation is not an anchor |
| `record` | the record concerned; filled when `via` is `should-have-loaded`, `trigger-fired` or `contradiction`, and only then |
| `recheck` | optional: a probe that is false now and would mean the noticing matters again — `exists <path>`, `missing <path>`, or `grep "<expression>" <path or glob>` |
| `steer-kind` | what the owner's words did: `correction`, `direction`, `choice`, `preference`, or `other(<what>)`; filled when `via` is `owner-steer`, and only then |
| `moment` | when asking would have made the steer unnecessary: `start`, `work` or `close`; filled when `via` is `owner-steer`, and only then |
| `missed-by` | the record, row or lens that should have caught it, or `none`; filled when `via` is `owner-steer` or `should-have-loaded`, and only then |
| `disposition` | `open`, then where the observation ended up |
| `held` | the learn passes that kept this observation open |

## Title and body

The title names what was noticed, as a thing. The body states the instance in 600 characters or fewer. No
line of the body opens with `Fix:`, `Proposal:` or `TODO:`: an observation that says what to do is a
proposal in the wrong folder.

## Closing dispositions

The engine writes these; nobody writes them by hand.

- `promoted → <label> (<proposal>)`: the noticing became, or joined, a record.
- `folded → <file or label> (<proposal>)`: it landed as an edit to how a record is found, a row, a lens, or
  a writing rule.
- `dropped — <reason>`: the owner rejected the proposal it supported, or a learn pass judged it not worth
  a home.
- `moot — <reason>`: its subject has left the project.
- `read (pass-nnn)`: a learn pass read it and no proposal used it.

## Do and Don't

- Do write one noticing with one anchor in a few lines. Don't build a case; a page of context is a
  proposal.
- Do state what happened. Don't state the fix.
- Do write it without looking at earlier observations. Don't search for an earlier instance or edit one to
  absorb this.
- Do give a `recheck` only where a probe can express it. Don't write a date or a condition nobody could
  observe.

## Examples

From a software project:

```markdown
---
uid: a3f29c0e
id: O-20260314-a3f29c0e
date: 2026-03-14
session: S-20260314-1c0e
via: lens:friction
anchor: scripts/release.sh
record: ""
recheck: ""
steer-kind: ""
moment: ""
missed-by: ""
disposition: open
held: []
---
# The release script asks for the version number three times

Each of the three stages prompts for the version and none passes it to the next. A mistyped second answer
produced a tag that did not match the changelog.
```

From a project that is not software, an owner's correction:

```markdown
---
uid: 5d07b1e4
id: O-20260203-5d07b1e4
date: 2026-02-03
session: S-20260203-9a2f
via: owner-steer
anchor: owner, 2026-02-03
record: ""
recheck: ""
steer-kind: correction
moment: start
missed-by: none
disposition: open
held: []
---
# A client's name was spelled the common way, not the way the client spells it

The owner asked that the name in `letters/2026-02-renewal.md` be spelled as the client's own letterhead
spells it. The draft had used the usual spelling of that surname.
```
