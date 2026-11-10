# How to write a decision

A decision is one file, `<label>.md`: a frontmatter block, a title, and the sections named below. Read the
Write card of `../language.md` before drafting one. A decision is drafted as a proposal and enters this
folder when the owner approves it; the engine then fills `uid`, `id`, `decided` and `approved-by`.

## Schema

The engine validates every decision against this block. The block changes through a `schema` proposal.

```vesta-schema
layout: flat
title: required
index:
  when: when
  why: why
  except: except
  paths: scopes
  triggers: triggers
payload-section: Decision
conditions: [falsifier-or-trigger, successor-pair, retired-reason]
fields:
  - name: uid
    type: text
    required: true
  - name: id
    type: text
    required: true
  - name: status
    type: enum
    values: [accepted, superseded, retired]
    required: true
    mutable: true
  - name: decided
    type: date
    required: true
  - name: approved-by
    type: text
    required: true
  - name: when
    type: text
    required: true
    mutable: true
  - name: why
    type: text
    required: true
    mutable: true
  - name: except
    type: text
    mutable: true
  - name: scopes
    type: list
    mutable: true
  - name: triggers
    type: triggers
    mutable: true
  - name: supersedes
    type: refs
  - name: superseded-by
    type: ref
    required-when: status in superseded
    mutable: true
  - name: retired-because
    type: text
    required-when: status in retired
    mutable: true
  - name: related
    type: refs
    mutable: true
sections:
  - name: Context
    required: true
  - name: Options considered
    required: false
  - name: Decision
    required: true
  - name: Consequences
    required: false
  - name: Warrant
    required: true
```

In the block, `required` marks a field that may not be empty, and `required-when` one that is filled
exactly when another field holds a named value. A field marked `mutable` may change after the record is
written; every other field is fixed once written. A store whose
fields for status, successor or retirement carry other names declares them under an optional `lifecycle`
key; this one uses the usual names and has none. `index` names the fields the index prints, and
`payload-section` the section a wording correction may not touch.

## Fields

| Field | Holds |
|---|---|
| `uid` | the internal id: eight characters the engine assigns once and never changes |
| `id` | the label people read and say, as `D-004`; the file is named by it |
| `status` | `accepted`, `superseded` or `retired` |
| `decided` | the date of approval |
| `approved-by` | a name or a reference given at the approval, for the record; `the owner` where none was |
| `when` | when to open this decision, in the words a task arrives in; never the decision restated |
| `why` | one line: what goes wrong if the decision is ignored |
| `except` | a concrete case the `when` line's words match and the decision does not cover |
| `scopes` | the folders the decision governs, as paths from the project root; a trailing `/` marks a folder |
| `triggers` | the revisit triggers, described below |
| `supersedes` | the decision or decisions this one replaces |
| `superseded-by` | the successor; filled when `status` is `superseded`, and only then |
| `retired-because` | why the subject has left the project; filled when `status` is `retired`, and only then |
| `related` | other decisions worth reading with this one |

One decision names another as `<label>@<uid>`, as `D-003@7f3a9c2e`. In body text, write the label alone.

The `when` line and the triggers are separate on purpose. A `when` line is matched against the task in
hand; a trigger is matched against the state of the project, and the two often share no word.

## Triggers

A trigger is a condition in the project that means the decision is due another look. Each has:

- `id`: `t1`, `t2`, … within its decision;
- `if`: the condition, written as it would be observed;
- `then`: the act owed; it opens with `apply`, `re-decide`, `re-derive`, `check`, `retire`, or
  `other(<what>)`;
- `probe`: optional; a condition the engine evaluates by reading the project — `exists <path>`,
  `missing <path>`, or `grep "<expression>" <path or glob>`;
- `resolved`: empty while the trigger is live; an anchor once the condition was met and handled.

A condition with two independent parts is two triggers.

## Title and sections

The body opens with one `# ` line: the decision in one sentence. The sections follow in this order.

| Section | Required | Holds |
|---|---|---|
| `## Context` | yes | the situation that makes the decision necessary |
| `## Options considered` | no | each option turned down, with the reason |
| `## Decision` | yes | the constraint alone: what is required or permitted |
| `## Consequences` | no | what follows from the decision |
| `## Warrant` | yes | the dated facts that ground it; `- False if:` lines; what nothing verifies |

An accepted decision states what would make it wrong: a line that opens `- False if:`, written in the
Warrant, or a trigger. The engine reads that one is present. Whether it could ever happen is the owner's reading at
approval.

## How a decision changes

| Change | Proposal kind | Effect |
|---|---|---|
| the `when`, `why` and `except` lines, the scopes, the triggers, the related list | `latch-edit` | edited in place |
| a typo, a moved path, a clearer sentence outside the title and the Decision section | `correct` | edited in place |
| a trigger whose condition was met and handled | `resolve-trigger` | `resolved` is filled |
| what the decision requires or permits | `supersede` | a successor is written; this one is marked `superseded` |
| the subject has left the project | `retire` | the status changes; nothing is deleted |

## Do and Don't

- Do write the Decision as the constraint alone. Don't carry versions, counts or lists in it; date them
  into the Warrant.
- Do write the `when` line in the words the task arrives in, and lean broad. Don't restate the decision as
  the `when` line, and don't widen it past any link to the decision.
- Do state `except` as a concrete case. Don't write "anything else".
- Do declare scopes at folder level. Don't scope to a single file; leave scopes out rather than guess.
- Do state the decision at the level of the general case. Don't generalize past what the Warrant supports.
- Do write a falsifier that could happen. Don't write "False if: the owner changes their mind": every
  decision is open to that, so it says nothing.
- Do replace a reversed decision with a successor. Don't edit what a decision requires in place.

## Examples

From a software project:

```markdown
---
uid: 7f3a9c2e
id: D-004
status: accepted
decided: 2026-03-14
approved-by: A. Reviewer
when: >-
  adding or changing a call to an outside service; choosing a timeout or a retry count; a
  request that hangs or fails now and then
why: an unbounded wait in one call stalls the whole job queue
except: calls between this project's own services, which use the internal client
scopes: [src/integrations/, src/http/]
triggers:
  - id: t1
    if: an outside service used here documents a response time above the timeout
    then: re-decide the timeout for that service
    probe: ""
    resolved: ""
supersedes: ""
superseded-by: ""
retired-because: ""
related: []
---
# Every call to an outside service sets a timeout of ten seconds or less and retries at most twice

## Context
Jobs run one at a time from a single queue. A call that never returns holds the queue.

## Options considered
- No timeout, rely on the service: rejected; one stalled call on 2026-03-10 held the queue for six hours.
- A timeout per service, tuned: rejected for now; nothing shows the services differ enough to pay for it.

## Decision
Every call to an outside service sets a timeout of ten seconds or less and retries at most twice.

## Warrant
- On 2026-03-10 one call with no timeout held the job queue for six hours (`docs/incidents/2026-03-10.md`).
- False if: a service this project depends on needs more than ten seconds for a normal response.
- Not checked: nothing verifies that each call sets a timeout.
```

From a project that is not software:

```markdown
---
uid: 2b9e41c7
id: D-002
status: accepted
decided: 2026-02-03
approved-by: A. Reviewer
when: >-
  quoting a figure, a date or a name in anything sent outside the team; preparing a report,
  a letter or a summary for a client
why: a figure copied from an earlier draft goes out after the source has changed
except: internal working notes, which may carry provisional figures marked as such
scopes: [reports/, letters/]
triggers:
  - id: t1
    if: the source sheet moves or is replaced by another system
    then: re-derive where figures are checked against
    probe: missing data/figures.csv
    resolved: ""
supersedes: ""
superseded-by: ""
retired-because: ""
related: []
---
# Every figure sent outside the team is checked against the source sheet on the day it is sent

## Context
Reports are drafted over several days while the source sheet keeps changing.

## Decision
Every figure, date and name in a document sent outside the team is checked against the source sheet on
the day of sending, and the document records that date.

## Warrant
- On 2026-01-28 a quarterly summary went out with two figures from a draft a week old (`reports/2026-q4/notes.md`).
- False if: the source sheet is frozen before drafting starts, so that drafts cannot go stale.
- Not checked: nothing verifies that the check was made; the recorded date is the only trace.
```
