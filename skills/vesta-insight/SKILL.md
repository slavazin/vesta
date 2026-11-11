---
name: vesta-insight
description: Review a finished task before reporting it done. Goes over what the session read, changed and was corrected on, writes short notes of what it noticed, and reports to the owner. Use when a task's work is finished, in the same conversation, before saying it is done. Say "short" for a session that changed little.
---

# Review a finished task

## When to run

When a task's work is finished, in the same conversation, before telling the owner it is done. It may
be run where `/vesta-hook` never ran. It needs Vesta set up in the project and engine 0.1.0 or later.

Where `$ARGUMENTS` holds `short`, run the short form. The short form is for a session that changed
little; the owner decides which sessions those are.

## Rules that hold throughout

- Run `apply` only for a proposal the owner has approved by its id in this conversation, after seeing its
  text. "Looks good", silence, an approval of a different proposal, and an approval given before the
  proposal was shown are not approval. Running `apply` is the record that the owner approved; `--ref` may
  add a commit or a note to it. Make every lasting change through a proposal. A file under `vesta/` that
  the owner edits by hand is logged by the engine; never edit a `SCHEMA.md` or `vesta.yml` by hand.
- Fill and correct a proposal that is still waiting, and its draft beside it, in place.
- Tell the owner about Vesta in plain words: decision, note, proposal, approve, reject. Name a decision
  by its label and title. Leave out the words the sheet uses for its own parts.
- Where a command prints a line that opens `Note:`, tell the owner what it says, in plain words. Name a file by
  its path.
- Report counts with what is behind them, never an assurance: a decision or a proposal by its label,
  a note by its title.

## What it does

The first part:

1. Bundle: what the session recorded as it went.
2. Marks: what came of each decision the session read.
3. Sweep: decisions that cover a changed file and were never read.
4. Contradictions: whether the work met what a decision says would make it wrong.
5. Steers: every time the owner corrected or redirected the work.
6. Rows: the project's own standing checks for the end of a task.
7. Lenses: the project's own questions about the session.
8. Mint: the notes are written, and the session is closed.

The second part:

9. Choices: whether something the owner chose should become a proposed decision.
10. Offers: at the most active setting, the choices the agent made alone are put to the owner.
11. Surface: what was written and what waits for the owner.

The short form is the bundle, the marks, the steers and the notes. A project's configuration may leave
steps out; the sheet lists the ones it prints.

## Procedure

1. **Find the project root:** the nearest folder at or above the working directory that holds
   `vesta/vesta.yml`. Where there is none, tell the owner to run `/vesta-init` and stop. Below, `vesta`
   stands for `python3 "<that root>/vesta/.engine"`; use `python` where `python3` is not found.
2. **Check the engine.** Run `vesta version`. Where the engine is older than 0.1.0, tell the owner to run
   `/vesta-init upgrade` and stop. Where the command fails because `vesta/.engine` is not there and
   `vesta/.engine.next` is, an upgrade stopped half-way: `/vesta-init upgrade` finishes it.
3. **Print the first part.** Run `vesta walk close`, with `--short` for the short form. Where the
   conversation never ran `/vesta-hook`, add `--ask -` and give on standard input what the session did:
   the engine then opens a session late and the sheet says so. Where what is printed says that the
   part is carried out aside, run the command it names, wait for it, and go on from step 5 with the
   command that one prints.
4. **Carry out the part** from top to bottom. Each section's **Do** line is an instruction for now. Work out what each section found, including nothing, as your own working: the owner is told only what the sheet's last part asks for. Several sections have you prepare a note: keep each one,
   and send them all in the single `vesta obs add` call the last section of the part asks for. That
   section ends by closing the session with `vesta session close`.
5. **Print the next part** with the command the first part ends on, and carry it out the same way. A
   sheet that ends by saying the walk is complete has no further part.
6. **Give the owner the report** the sheet ends with, once, in its order.
7. **Decide proposals with the owner.** Put each proposal drafted in this session to the owner in one
   or two plain sentences: what would change, and what it would cost from now on. On a yes that names
   it, run `vesta apply <id>`; on a no, `vesta reject <id> --reason -` with their reason. What the owner does not decide stays waiting and is listed at the
   next start.
8. **If the owner corrects something after the report,** do what the sheet's last part said for that
   case: it differs by machine, and the sheet printed only what holds here.

## Do / Don't

- Do work from the bundle first and memory second. Don't rebuild the session from recall alone: the
  jots were written while the detail was in view.
- Do write each note as the sheet prints, and move on. Don't build a case.
- Do list every correction, including ones that feel minor. Don't file agreement as a correction, and
  never ask the owner whether they have more.
- Do answer every question the sheet asks; "nothing" is an answer. Don't file an answer its own
  counter-question dissolves, and don't write a note to have something to show.
- Don't look at earlier notes to see whether something was noticed before: don't open
  `vesta/observations/`, and don't run `obs list`. Counting what recurs is the job of `/vesta-learn`; a
  session that checks its own noticing against the pile is grading itself.
- Do put every choice of the owner's through the test the sheet prints, in order. Don't draft a
  decision for a preference, a one-off instruction, something the project itself already enforces, or
  a situation an existing decision covers: change that decision, or do nothing.
- Do, at the most active setting, put a real choice you made alone in front of the owner. Don't turn
  that into asking for corrections, and don't offer more than five things.

## What this does not guarantee

This is the session reviewing its own work, and it under-reports what the session did not notice. The
search for unread decisions reaches only decisions that name paths covering a changed file; a project
whose work is not in files gets nothing from it. A review that is skipped records nothing: the next
start reports the session left open and recovers its jots, and no more. Nothing forces this skill to
be run. Nothing verifies that the sheet was carried out honestly. The engine records that a proposal was applied and cannot tell whether the owner approved it.
