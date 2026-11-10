# How to write a proposal

A proposal is one drafted lasting change, waiting for the owner. It is one file, `<label>.md`. A proposal
that would create a record has that record's full text beside it in `<label>.draft.md`. Start one with the
engine's `propose` command, which writes the frontmatter and names the files to fill. Read the Write card
of `../language.md` before filling them.

## Schema

The engine validates every proposal against this block. The block changes through a `schema` proposal.

```vesta-schema
layout: flat
title: required
conditions: []
fields:
  - name: uid
    type: text
    required: true
  - name: id
    type: text
    required: true
  - name: kind
    type: enum
    values: [add, supersede, merge, retire, latch-edit, correct, resolve-trigger, row, lens, language, schema, config]
    required: true
  - name: target
    type: text
    required: true
  - name: drafted
    type: date
    required: true
  - name: source
    type: text
    required: true
  - name: evidence
    type: refs
    mutable: true
  - name: sessions
    type: integer
    required: true
  - name: bar
    type: text
    mutable: true
  - name: standing-cost
    type: text
    required: true
  - name: outcome
    type: text
    mutable: true
sections:
  - name: Why
    required: true
  - name: Counter-case
    required: true
  - name: Cheaper homes considered
    required: false
  - name: Change
    required: true
  - name: Replaced
    required: false
```

In the block, `required` marks a field that may not be empty, and `required-when` one that is filled
exactly when another field holds a named value. A field marked `mutable` may change after the record is
written; every other field is fixed once written.

## Fields

| Field | Written by | Holds |
|---|---|---|
| `uid`, `id` | `propose` | the internal id and the label, as `P-007` |
| `kind` | `propose` | one of the kinds below |
| `target` | `propose` | a store name for `add`; otherwise a record label, a trigger as `<label>/t1`, or a file path |
| `drafted` | `propose` | the date |
| `source` | `propose` | `pass-nnn`, a session id, or `init` |
| `evidence` | `propose` | the observations the proposal rests on |
| `sessions` | `propose` | how many separate sessions the evidence comes from; computed, never typed |
| `bar` | the drafter | the evidence the proposal claims to have, in words |
| `standing-cost` | `propose` | what the change would cost every later session; computed |
| `outcome` | `apply`, `reject` | empty while pending; then who decided, when, and for a rejection why |

## Title and sections

The title says what would change, in one line.

| Section | Required | Holds |
|---|---|---|
| `## Why` | yes | the shape the evidence shares, stated without the particular files; two to five sentences |
| `## Counter-case` | yes | where this would misfire or reach too far, and why it is proposed anyway |
| `## Cheaper homes considered` | no | each cheaper way to prevent the shape, with the reason it falls short; left out at a session's close |
| `## Change` | yes | one block, in the form its kind takes |
| `## Replaced` | no | added by the engine on approval: every value or text the change replaced |

## Kinds

| Kind | Target | The Change section holds |
|---|---|---|
| `add` | a store name | `See <label>.draft.md` |
| `supersede` | a record | `See <label>.draft.md`; the draft's `supersedes` names the target |
| `merge` | two or more records, separated by commas | `See <label>.draft.md`; the draft's `supersedes` names every target |
| `retire` | a record | a `vesta-set` block with `retired-because` |
| `latch-edit` | a record | a `vesta-set` block naming the fields that say how the record is found |
| `resolve-trigger` | a trigger | a `vesta-set` block with `resolved` |
| `correct` | a record | find/replace pairs; never in the title or in the section that states what the record requires |
| `row` | a walk file | a `vesta-row` block |
| `lens` | a walk file | a `vesta-row` block |
| `language` | `language.md`, or a walk file's prose section | find/replace pairs |
| `schema` | a `SCHEMA.md` | find/replace pairs |
| `config` | `vesta.yml` | a `vesta-set` block with dotted keys |

In a draft, write `NEW` for `uid` and `id`, and leave `decided` and `approved-by` empty: the engine fills
all four on approval.

### A `vesta-set` block

It names fields and their whole new values:

````markdown
```vesta-set
when: >-
  adding or changing a call to an outside service; choosing a timeout or a retry count; a
  request that hangs or fails now and then; a job that never finishes
scopes: [src/integrations/, src/http/, src/jobs/]
```
````

For `triggers` the block gives the whole new list. For `config` the keys are dotted paths, as
`reminders.learn.open-observations: 40`.

### A `vesta-row` block

It names the operation and the cells:

````markdown
```vesta-row
op: add
id: ""
fires-when: the task changes how a release is cut
fires-on: scripts/release*
consult: "`docs/releasing.md`"
owed-act: read the checklist before changing a stage
level: standard
```
````

`op` is `add`, `change` or `remove`. `change` and `remove` name the row by `id`, or the lens by `lens`;
`change` gives only the cells that change. For a lens the cells are `lens`, `angle`, `counterfactual` and
`level`. The engine writes `origin` itself.

### Find/replace pairs

For prose only. The fences are four backticks, so the text may hold a three-backtick fence:

`````markdown
````find
<text that occurs exactly once in the target file>
````
````replace
<the text that takes its place; may be empty>
````
`````

A `find` that occurs zero times, or more than once, is refused.

## Do and Don't

- Do state the change at the level of the shape. Don't copy the observations into it: three instances
  under one heading are three observations, not a decision.
- Do say in Counter-case where the change would misfire. Don't leave it as "none".
- Do propose the cheapest change that would have prevented the shape. Don't answer every shape with a new
  decision; a wider `when` line on an existing one costs less.
