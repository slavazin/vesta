# Start walk

Session: S-TOKEN
Opened session S-TOKEN.
Task: raise the timeout
Paths given: `src/http/client.py`

Steps of this walk: 1. Recall · 2. Triggers · 3. Rows · 4. Lenses · 5. Notices

Carry out each section from top to bottom; its **Do** line is an instruction for now. Run each command named below as `python3 "<root>/vesta/.engine" <command>`.

## 1. Recall

### decisions

Reached by the paths given, loaded, and printed in full:

---- D-001, in full (vesta/decisions/D-001.md) ----
---
uid: 0000000a
id: D-001
status: accepted
decided: 2026-01-05
approved-by: A. Reviewer
when: calling an outside service
why: a stale figure goes out
except: ""
scopes: [src/http/]
triggers: []
supersedes: []
superseded-by: ""
retired-because: ""
related: []
---
# Every figure is checked on the day it is sent

## Context
Reports are drafted over several days.

## Decision
Every figure is checked against the source on the day of sending.

## Warrant
- False if: the source is frozen before drafting starts.
---- end of D-001 ----

---- D-004, in full (vesta/decisions/D-004.md) ----
---
uid: 0000000d
id: D-004
status: accepted
decided: 2026-01-05
approved-by: A. Reviewer
when: choosing a timeout
why: a stale figure goes out
except: ""
scopes: [src/http/client.py]
triggers: []
supersedes: []
superseded-by: ""
retired-because: ""
related: []
---
# Every figure is checked on the day it is sent

## Context
Reports are drafted over several days.

## Decision
Every figure is checked against the source on the day of sending.

## Warrant
- False if: the source is frozen before drafting starts.
---- end of D-004 ----

Index of the other records:

```
D-002  [docs/]
  when:   writing the user guide
  why:    a stale figure goes out

D-003
  when:   naming a release
  why:    a stale figure goes out
```

Counts: 4 records in force; 2 loaded in full; 2 index blocks.

**Do:** A record printed in full above is loaded: read it. Then read every index block against the task: the paths it touches, the parts of the project it involves, and the kind of work it is. For each block whose `when` line matches or could plausibly match, run `load <id>` and read the record. Load a doubtful match: a record that turns out not to apply costs a glance. Don't act on an index block: it says when to open a record, never what the record decides.

Where two loaded records conflict, show the owner both and don't choose between them. Where a loaded record does not match the project as it stands, compare the mismatch with the record's `False if:` lines and its `triggers`; then tell the owner what does not match. State the result as a count with the ids behind it, or as `none matched (index read)`.

Ask the owner a question only where two loaded records conflict or one reads false.

## 2. Triggers

- **D-003/t1**, probe: fired
  if: the release notes file is gone
  then: re-decide where releases are named
- **D-003/t2**, probe: no probe
  if: a second product ships from this folder
  then: check the naming still holds

**Do:** Read each `if` against the project as it stands. Read all of them: a trigger can fire on work that its record's `when` line does not name. For each `if` that holds, and each whose probe state is `fired`: run `load <record id> --by trigger`, do the work in the light of that record, and tell the owner which condition was met. Don't work around a fired trigger. A probe state that opens `error` means the engine could not evaluate the probe: judge that `if` yourself, and tell the owner that this condition could not be checked automatically and was judged by reading.

## 3. Rows

- **start-01** (judge)
  fires when: the task rests on how something outside the project behaves — a tool, a service, a standard, a reference work
  consult: that thing's own documentation or text
  owed act: check the claim at the source before building on it

**Do:** For each row marked `fired`, and each row marked `judge` whose `fires when` condition holds for this task: open the one thing its `consult` names and do the one act it owes. Don't act on a row whose condition does not hold. Keep a line for each row acted on: the brief gives it to the owner as a standing check, by what it asked, without its id.

## 4. Lenses

- **said-before**
  angle: Which part of this task has the owner asked for, corrected, or explained in an earlier session, and where is the earlier answer written down?
  counterfactual: Is it written down where this session would have found it without being told, or would the owner have had to say it again?

**Do:** Answer each angle for this task, then put its counterfactual to your answer. Drop an answer the counterfactual dissolves. An answer that survives changes the plan before work starts, or is noted with `jot -`. "Nothing" is an acceptable answer.

Don't put these questions to the owner; the brief names an answer only where it changed the plan.

## 5. Notices

none

**Do:** Tell the owner each notice in one plain line: what is waiting for their decision, that `/vesta-learn` is worth running where a learn pass is due, and that `/vesta-backfill` can read back the tasks that ended without a review, where the section says so. Where this section says `none`, say nothing about it.

---

Give the owner the brief now, in this order and nothing else:

- the task, restated in one or two lines;
- the decisions that apply, each by its label and title with the one constraint it places on this task; where none applies, say that none matched, and that the one-line summary of every decision was read;
- each condition for revisiting a decision that holds now, with the decision and what it calls for; where none holds, say so;
- each standing check of this project that you carried out;
- one line for each answer above that changed the plan;
- what is waiting for the owner;
- any two decisions that conflict, both shown, for the owner to decide.

Use plain words with the owner: decision, note, proposal. Name a record by its label and title. Leave out the sheet's own words: walk, row, lens, latch, bar, ladder, sweep, mark, bundle, trigger, index; and never give an internal id.

Then start the work, and keep two habits while working. At the moment the owner corrects or redirects the work, run `jot --steer -` and give their words on standard input. For anything else you notice that is not worth stopping for, run `jot -`. A jot takes seconds; don't stop to analyse it.

The walk is complete: no further part follows.
