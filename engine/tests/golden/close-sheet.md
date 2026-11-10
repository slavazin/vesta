# Close walk

Session: S-TOKEN
It was already open: opened 2026-01-05T09:00:00Z.
Task: raise the timeout

Steps of this walk: 1. Bundle · 2. Marks · 3. Sweep · 4. Contradictions · 5. Steers · 6. Lenses · 7. Mint · 8. Choices · 9. Surface

Carry out each section from top to bottom; its **Do** line is an instruction for now. Run each command named below as `python3 "<root>/vesta/.engine" <command>`.

## 1. Bundle

Session S-TOKEN, opened 2026-01-05T09:00:00Z, open.

Tasks, in the owner's words:
1. raise the timeout

Records loaded:
- D-002, Every figure is checked on the day it is sent (by scope; not marked yet)

Jots, in order:
- 2026-01-05T09:00:05Z [steer] twenty seconds, not thirty

Paths changed since the session opened, less what the engine wrote:
- src/http/client.py

Triggers whose probe state changed during the session:
none

**Do:** Read this first. It was recorded as the session went, and it outranks what you recall of the session.

## 2. Marks

- D-002, Every figure is checked on the day it is sent (loaded by scope)

**Do:** Mark every record listed here in one command, as `mark <id>=applied <id>=not-applicable`. Mark a record `applied` where the work followed it, and `not-applicable` where it was read and did not bear on the work. Where this section says `none`, there is nothing to mark.

## 3. Sweep

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

**Do:** For each record printed here, ask whether it governed work this session did. Where it did, run `mark <id>=should-have-loaded` and prepare an observation with `via: should-have-loaded`, with `record` and `missed-by` both the record's id, stating the words the task arrived in that the record's `when` line lacks. To prepare an observation is to keep it for the one `obs add` call a later section asks for; nothing is written yet. Where the record did not bear on the work, do nothing.

A sweep that finds nothing does not show that nothing was missed: it reaches only records whose `scopes` cover a path this session changed.

## 4. Contradictions

- **D-002, Every figure is checked on the day it is sent**
  False if: the source is frozen before drafting starts.
- **D-001, Every figure is checked on the day it is sent**
  False if: the source is frozen before drafting starts.
- **D-004, Every figure is checked on the day it is sent**
  False if: the source is frozen before drafting starts.

Triggers whose probe state changed during the session:
none

**Do:** For each `False if:` line and each trigger printed here, ask whether this session's work or what it found met it. Where one did, prepare an observation for the one `obs add` call a later section asks for: `via: contradiction` for a `False if:` line or `via: trigger-fired` for a trigger, with `record` the record's id. Tell the owner in one plain sentence, naming the decision by its label and title. Don't leave a record that reads false as it is, and don't edit it by hand: the observation is what brings it to a learn pass.

## 5. Steers

Corrections captured while the session ran:
- 2026-01-05T09:00:05Z twenty seconds, not thirty (from jot)

Records in force, for naming the one that should have caught a correction:
- D-001  when: calling an outside service
- D-002  when: writing the user guide
- D-003  when: naming a release
- D-004  when: choosing a timeout

**Do:** Go through the conversation and list every time the owner corrected the work, redirected it, chose between alternatives, or stated a preference. Start from the corrections captured above and add what they miss. Agreement with a recommendation is not a steer, and neither is a request for status.

For each steer, prepare an observation for the one `obs add` call a later section asks for, with `via: owner-steer`: the owner's words quoted or closely paraphrased; its `steer-kind`; its `moment`, the point at which asking would have made the steer unnecessary; and `missed-by`, which names the record from the list above, or the row or lens of this sheet, that should have caught it, or `none`. Don't ask the owner for more corrections.

## 6. Lenses

- **friction**
  angle: Which step of this session took more effort than the task warranted — named as a step, with where it happened — and would the next session pay the same cost?
  counterfactual: Was it a one-off, or a difficulty the task itself carried, blamed on the step that met it?
- **first-wrong**
  angle: Where was the first attempt wrong, and what did it take to find out?
  counterfactual: Was it a slip anyone makes, or a piece of standing knowledge that was missing?
- **missing-record**
  angle: What decision or instruction, had it been written down, would have shaped this work from the start?
  counterfactual: Where would that record misfire or reach too far on the next task?
- **unnoticed**
  angle: What went unnoticed for a while that a record, a checklist or an automatic check could have shown sooner?
  counterfactual: What about it could no record or check have foreseen?

**Do:** Answer every angle for this session, then put its counterfactual to your answer. "Nothing" is an acceptable answer and writes nothing. Drop an answer the counterfactual dissolves. An answer that survives becomes a prepared observation with `via: lens:<name>` and an anchor that a made-up answer could not supply: a path or a record id. Something worth recording that no lens asked for is prepared with `via: off-map`. Each is kept for the one `obs add` call the next section asks for.

Don't put these questions to the owner; the close report carries what the answers found.

## 7. Mint

How to write one: `vesta/observations/SCHEMA.md`.
`obs add` reads a JSON array on standard input, one item for each observation:

```json
[
  {"title": "…", "body": "…", "via": "…", "anchor": "…", "record": "…", "recheck": "…", "steer-kind": "…", "moment": "…", "missed-by": "…"}
]
```

The engine fills the rest: the id, the date, the session, and where the observation stands.

**Do:** Read the Fields table of the SCHEMA file named above: it gives the values each key takes and when a key is filled. Read the *Write card* of `vesta/language.md`. Then send every prepared observation in one call of the `obs add` command shown above, giving the JSON array on standard input, one item for each. Leave out a key that does not apply. A jot in the bundle that no prepared observation covers is sent as one, with `via: jot`. One noticing, one anchor, no fix. Don't look at earlier observations to see whether something was noticed before. Where the command refuses, nothing was written: correct the items it names and send the whole array again. Where nothing was prepared, send nothing.

Then run `session close`.

---

This part ends here. Once every **Do** above is carried out, print the next part with `walk close --from choices --session S-TOKEN`.

=====

# Close walk

Session: S-TOKEN
This session is closed: the sheet shows what it recorded, and it takes no further mark, jot or observation.
Task: raise the timeout

Steps of this walk: 1. Bundle · 2. Marks · 3. Sweep · 4. Contradictions · 5. Steers · 6. Lenses · 7. Mint · 8. Choices · 9. Surface

Carry out each section from top to bottom; its **Do** line is an instruction for now. Run each command named below as `python3 "<root>/vesta/.engine" <command>`.

## 8. Choices

What the owner chose in this session, as written down:
none

The test for a choice (`vesta/walks/close.md`, Choices):

The test for turning something the owner decided in a session into a proposed decision. Apply it in order;
the first part that fails ends it, and the choice stays a note.

1. **There was a real alternative.** At least one other option was on the table and was turned down. A
   plain instruction ("use the blue one") with nothing rejected is a preference.
2. **It will come up again.** The situation can be described without this task: finish the sentence "the
   next time someone is …". If the sentence cannot be finished, it was a one-off.
3. **The project does not already settle it.** If a file, a setting or the code now enforces the choice,
   the project is the record; write nothing.
4. **No decision already covers it.** Read the `when` lines listed with this step. Where one covers the
   same situation, the choice changes or confirms that decision — propose an edit to it, or nothing — and
   does not become a second record.

A choice that passes all four is proposed as a decision, with the owner's words as its evidence.

Records in force:
- D-001  when: calling an outside service
- D-002  when: writing the user guide
- D-003  when: naming a release
- D-004  when: choosing a timeout

How to write a record of each store:
- `decisions`: `vesta/decisions/SCHEMA.md`

**Do:** Put each choice listed here through the test printed above, in order. A choice that fails any part stays an observation, and nothing more is done with it.

For a choice that passes: where a record in force already covers the situation, propose a change to that record with `propose latch-edit --target <id>` or `propose supersede --target <id>`, or propose nothing. Otherwise run `propose add --target decisions --evidence <that observation> --source S-TOKEN`, fill the proposal and its draft under the store's SCHEMA.md and `vesta/language.md`, and run `proposals <id>`: read the note it prints on records that may already cover the draft, and correct what it says is wrong. This is the one case where a single observation is enough for a new record: the owner has already decided it.

## 9. Surface

Observations this session wrote, by where each came from:
- lens:friction (1)
  - O-TOKEN, The export asks for the date twice
- owner-steer (1)
  - O-TOKEN, Twenty seconds was wanted

Proposals waiting for the owner's decision when this sheet was printed; `proposals` lists them as they stand after any drafted since:
none

Reminders:
none

**Do:** Give the owner the close report set out at the end of this sheet. Present each proposal drafted in this session for their decision. Run `apply` or `reject` only as the owner decides, by id, and leave the rest waiting.

Keep the report to its lines; add nothing to it.

---

Give the owner the close report now, once, in this order. Draw each line from what this walk's sections found, in every part of it, and give it as a sentence. Leave out a line this walk had no section for. The notes written are the ones `obs add` listed:

- the decisions read in this session, each by its label and title with what came of it: applied, or read and did not bear;
- each decision that should have been read and was not, or that none was found;
- each decision whose stated condition for being wrong or for being revisited this session met, or that none was;
- how many notes were written, with their titles, grouped by where each came from;
- each proposal waiting for the owner's decision, with its label, what it would change and what it would cost from now on;
- what is waiting for the owner besides: each reminder this sheet printed.

Use plain words with the owner: decision, note, proposal, approve, reject. Name a decision or a proposal by its label and title, and a note by its title. Leave out the sheet's own words: walk, row, lens, latch, bar, ladder, sweep, mark, bundle, trigger, index; and never give an internal id.

If the owner corrects something after this report, run `jot --steer -` with their words. The engine opens a session to hold it, and the next start will offer to close that session.

The walk is complete: no further part follows.
