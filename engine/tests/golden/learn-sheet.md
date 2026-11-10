# Learn walk

Pass: pass-001, opened 2026-01-07T09:03:00Z
This pass was opened now. It reads the 3 notes open at this moment; a note written later waits for the next pass.
The owner's question: why does the date come up twice?

Steps of this walk: 1. Window · 2. Counts · 3. Trigger review · 4. Consolidate · 5. Group · 6. Route · 7. Draft · 8. Gate · 9. Seal

Carry out each section from top to bottom; its **Do** line is an instruction for now. Run each command named below as `python3 "<root>/vesta/.engine" <command>`.

## 1. Window

pass-001 reads 3 notes, from 3 sessions.

The notes still open, each in full:

O-TOKEN · date: 2026-01-05 · session: S-TOKEN · via: lens:friction · anchor: src/http/client.py · disposition: open
  The export asks for the date twice
    Both stages prompt for it.

O-TOKEN · date: 2026-01-06 · session: S-TOKEN · via: owner-steer · anchor: src/http/client.py · steer-kind: correction · moment: start · missed-by: D-004 · disposition: open
  Twenty seconds was wanted
    Both stages prompt for it.

O-TOKEN · date: 2026-01-07 · session: S-TOKEN · via: owner-steer · anchor: src/http/client.py · steer-kind: choice · moment: start · missed-by: none · disposition: open
  The owner chose plain numbers
    Both stages prompt for it.

Notes whose `recheck` fires now: none

Read by the last three passes and archived with nothing done (id, where it came from, title):
none

Proposals the owner turned down (`vesta/log/admissions.md`):
none

Trigger review: never run; passes sealed so far: 0.

**Do:** This is the whole input of the pass. Read all of it before grouping anything.

An open note that matches the shape of a title read by an earlier pass counts together with it. A shape that matches a proposal the owner turned down is shown to the owner with that rejection beside it.

Where the last line reports three or more passes since the trigger review last ran, and this sheet has no Trigger review section, print this part again with `walk learn --with trigger-review` before going on.

## 2. Counts

From the sessions that ended up to now; no earlier pass is on record:

For each decision in force, the sessions that read it and what each said came of it:
- read by no session: D-001, D-002, D-003, D-004
- sessions that read no decision: 3

Notes of this pass by `via`, where it came from:
- lens:friction: 1
- owner-steer: 2

Notes of this pass by `missed-by`, what should have caught it:
- D-004: 1
- none: 1

**Do:** These figures point at where to look and decide nothing. Each is a lower bound: a miss nobody noticed is not counted. Read each figure alone. Put the records in no order by them, add none of them together, and never propose retiring a record because few sessions read it.

## 3. Trigger review

Live triggers, each with what its probe finds now:
- **D-003/t1**, probe: fired
  if: the release notes file is gone
  then: re-decide where releases are named
- **D-003/t2**, probe: no probe
  if: a second product ships from this folder
  then: check the naming still holds

What would make each record in force wrong:
- D-001: False if: the source is frozen before drafting starts.
- D-002: False if: the source is frozen before drafting starts.
- D-003: False if: the source is frozen before drafting starts.
- D-004: False if: the source is frozen before drafting starts.

**Do:** Read each trigger and each `False if:` line against the project as it stands. One whose condition holds becomes a group of its own in the Group section, naming the record. One whose probe reports an error is told to the owner.

## 4. Consolidate

Pair 1: D-001 and D-002
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
---- D-002, in full (vesta/decisions/D-002.md) ----
---
uid: 0000000b
id: D-002
status: accepted
decided: 2026-01-05
approved-by: A. Reviewer
when: writing the user guide
why: a stale figure goes out
except: ""
scopes: [docs/]
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
---- end of D-002 ----

Pair 2: D-001 and D-003
D-001 is printed in full above.
---- D-003, in full (vesta/decisions/D-003.md) ----
---
uid: 0000000c
id: D-003
status: accepted
decided: 2026-01-05
approved-by: A. Reviewer
when: naming a release
why: a stale figure goes out
except: ""
scopes: []
triggers:
  - id: t1
    if: the release notes file is gone
    then: re-decide where releases are named
    probe: missing docs/releases.md
    resolved: ""
  - id: t2
    if: a second product ships from this folder
    then: check the naming still holds
    probe: ""
    resolved: ""
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
---- end of D-003 ----

Pair 3: D-001 and D-004
D-001 is printed in full above.
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

Pair 4: D-002 and D-003
D-002 is printed in full above.
D-003 is printed in full above.

Pair 5: D-002 and D-004
D-002 is printed in full above.
D-004 is printed in full above.

Pair 6: D-003 and D-004
D-003 is printed in full above.
D-004 is printed in full above.

**Do:** For each pair, ask whether the two bind the same situation.

- Where they say the same thing, propose a `merge` into one record that states it once.
- Where they conflict, show the owner both, and propose the `supersede` or `merge` their answer
  implies.
- Where they are distinct, propose an `except` line on each that names the other's case, or nothing.

A pair is a candidate and no finding: shared words are not shared meaning. Read both before saying anything about them.

## 5. Group

Shapes (`vesta/walks/learn.md`):

Group observations by what they share once the particular file, task and day are removed. A good shape
name could describe an instance that has not happened yet. Some shapes, as examples and not a list to fit
things into: the same correction given twice; a record that exists and was not loaded; a question the owner
had to raise that nothing asked; the same step costing effort each time; a record contradicted by what a
session found.

The owner's question: why does the date come up twice?

**Do:** Group the notes of the Window section that share a shape, and name each shape without the particular file or task. For each group give its ids, whether the match is tight or loose, and how many separate sessions it comes from. List the notes in no group, each with what a second instance would look like.

For noise, run `obs dispose <id> --as "dropped — <reason>"`; for a note whose anchor no longer resolves or whose subject has left the project, `--as "moot — <reason>"`. Never merge two shapes into a vaguer one to reach a count.

For each group, say whether anything written down in advance could have prevented it. Where nothing could, the group changes how such things get noticed, never what a writer is asked to do.

Where the owner gave a question, answer it from the Window section.

## 6. Route

Bars (`vesta/walks/learn.md`):

The evidence a proposal needs before it is drafted. A count nominates; the owner decides. Two observations
from one session count as one.

| Proposal | Bar |
|---|---|
| `latch-edit` — widen a `when` line, add a scope, add an `except` line | one `should-have-loaded` observation, or one owner steer whose `missed-by` names the record |
| `resolve-trigger` | the trigger's condition was met and the work it owed is done, with an anchor |
| `correct` | the record's decision is unchanged; any one observation |
| `add` | the same shape from two or more separate sessions; or one choice the owner made between real alternatives; or a `recheck` that fired |
| `supersede` | a falsifier or trigger of the record was met, with an anchor; or the owner reversed the decision |
| `merge` | two accepted decisions bind the same situation and say the same thing, or the owner has said which of two conflicting ones stands |
| `retire` | the record's subject has left the project, with an anchor. Never because the record was rarely loaded |
| `row` — add | the same shape from two or more sessions, and no existing record's `when` line could carry it |
| `lens` — add | two or more owner steers from separate sessions, of one shape, that no record, row or lens caught, and that no row or record could carry |
| `row`, `lens` — change or remove | two or more observations whose `missed-by` or `via` names it; remove only where its condition or question no longer applies to the project |
| `language` | the same wording problem in two or more records, or a term needed twice |
| `schema`, `config` | the owner asks, or the same structural gap from two or more sessions |

A shape that returns after a proposal about it was rejected is shown to the owner with the earlier
rejection beside it.

Ladder (`vesta/walks/learn.md`):

Route each group to the lowest rung that would have prevented it, and say why each lower rung falls short.
Rungs 1 to 5 add nothing a later session pays for. Rungs 6 to 8 do, and the proposal says how much.

1. **Nothing.** Nothing written in advance could have prevented it, or preventing it costs more than
   meeting it again. Leave it to be archived as read.
2. **Fix it in the project.** A template, a checklist or an automatic check in the project itself would
   stop it. Tell the owner; Vesta does not make that change.
3. **Edit how an existing decision is found, or merge two that say the same thing.** The record exists and was not loaded: widen its `when` line, add a
   scope, add an `except` line.
4. **Correct or replace an existing decision.** The record was loaded and was wrong or incomplete.
5. **Change an existing row or lens, or add a project term.** It asked too narrowly, too late, or the
   wrong thing; or two words were used for one thing.
6. **Add a decision.** A real choice keeps being made again.
7. **Add a row.** A check at a fixed moment, pointing at one thing to consult, would have caught it.
8. **Add a lens.** Only a standing open question would have caught it, and no record can hold the answer.

**Do:** For each group that meets a bar: choose the lowest rung of the ladder that would have prevented the shape, and name which part of which record, row or lens the evidence points at. Note the lower rungs you considered and why each falls short.

A group that meets no bar is kept open by name at the seal, or left to be archived as read. Adding nothing is a normal result of a pass.

## 7. Draft

- how a proposal is written: `vesta/proposals/SCHEMA.md`
- the writing rules: `vesta/language.md`
- the kinds of change this project allows: `add`, `supersede`, `merge`, `retire`, `latch-edit`, `correct`, `resolve-trigger`, `row`, `lens`, `language`, `schema`, `config`
- the source to give each proposal of this pass: `pass-001`

**Do:** For each routed group, run `propose <kind> --target <target> --evidence <ids> --source pass-001` and fill the proposal: the shape at its general level, the counter-case, the cheaper homes considered, the change. A proposed record states the general constraint, never a list of the instances.

Then put five questions to each draft, and correct what they find:

- Is it true?
- Would its `when` line be recognized by someone starting the task it should catch?
- Does an existing record already cover it? `proposals <id>` prints the records that may.
- Is it stated at the level of the shape?
- Does every claim have an anchor?

`proposals <id>` also says what still stops the proposal from being applied; leave none of that standing. Where no group was routed, draft nothing.

---

This part ends here. Once every **Do** above is carried out, print the next part with `walk learn --with trigger-review --from gate`.

=====

# Learn walk

Pass: pass-001, opened 2026-01-07T09:03:00Z
This pass was already open, and goes on from where it was left. It reads the 3 notes that were open when it opened.
The owner's question: why does the date come up twice?

Steps of this walk: 1. Window · 2. Counts · 3. Trigger review · 4. Consolidate · 5. Group · 6. Route · 7. Draft · 8. Gate · 9. Seal

Carry out each section from top to bottom; its **Do** line is an instruction for now. Run each command named below as `python3 "<root>/vesta/.engine" <command>`.

## 8. Gate

- P-001 · add decisions · Change one thing · standing cost: one short block more read at every start · drafted today
  evidence: 1 note · sessions they come from: 1 · drafted by: init
  Why:
    It keeps going wrong.
  Counter-case:
    It may reach too far.

**Do:** Present every proposal above to the owner in one message. For each: its label, what would change in one or two plain sentences, how many notes and sessions it rests on, what it would cost from now on, and the case against it. `proposals <id>` prints one in full.

Take the owner's decision on each by its label: approve, reject with a reason, leave it waiting, or change it and present it again. Run `apply <id>` or `reject <id> --reason -` exactly as decided; `--ref <commit or note>` adds a reference to the record. Never approve on the owner's behalf: "looks good", silence, and an approval of a different proposal are not approval.

Where nothing is waiting, say so and go on.

---

This part ends here. Once every **Do** above is carried out, print the next part with `walk learn --with trigger-review --from seal`.

=====

# Learn walk

Pass: pass-001, opened 2026-01-07T09:03:00Z
This pass was already open, and goes on from where it was left. It reads the 3 notes that were open when it opened.
The owner's question: why does the date come up twice?

Steps of this walk: 1. Window · 2. Counts · 3. Trigger review · 4. Consolidate · 5. Group · 6. Route · 7. Draft · 8. Gate · 9. Seal

Carry out each section from top to bottom; its **Do** line is an instruction for now. Run each command named below as `python3 "<root>/vesta/.engine" <command>`.

## 9. Seal

- O-TOKEN · The export asks for the date twice · cited by no waiting proposal · kept open by 0 earlier passes · at the seal: archived as read unless named
- O-TOKEN · Twenty seconds was wanted · cited by no waiting proposal · kept open by 0 earlier passes · at the seal: archived as read unless named
- O-TOKEN · The owner chose plain numbers · evidence of P-001, which waits for the owner · kept open by 0 earlier passes · at the seal: kept open

**Do:** Name the notes to keep open for a later pass, each with what it waits for. A note that is evidence of a waiting proposal is kept open without being named. One kept open three times already is archived unless the owner says otherwise; ask them about each such note.

Then run `pass seal --note -` and give these lines on standard input: one for each of `Groups:`, `Ungrouped:`, `Consolidation:`, `Not done:`, and one `Waiting <id>: <what it waits for>` line for each note to keep open. `Groups:` and `Ungrouped:` are the counts from the Group section; `Not done:` names anything this pass skipped, or says `nothing`; `Consolidation:` says what was done about the pairs, where there were any. `--hold <id>,<id>` keeps notes open too, with no reason recorded.

Every other note still open is archived as read by pass-001, and the pass ends.

---

Report the pass to the owner now, once, from the note `pass seal` printed: how many notes were read and from how many sessions; how many groups there were and how many notes fell in none; each proposal with what became of it; each note kept open, by its title, and what it waits for; whether the conditions for revisiting decisions were gone through and what that found; what was done about decisions that say the same thing; and what the pass did not do.

Use plain words with the owner: decision, note, proposal, approve, reject. Name a record by its label and title, and a note by its title. Leave out the sheet's own words: walk, row, lens, latch, bar, ladder, sweep, mark, bundle, trigger, index, window, held; and never give an internal id.

The walk is complete: no further part follows.
