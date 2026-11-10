---
name: vesta-learn
description: Go through the notes that sessions have left and decide with the owner what, if anything, should change for good. Groups the notes, proposes the cheapest change that would have prevented each recurring thing, takes the owner's yes or no on every proposal, and files the rest. Use when the owner asks for it, after a reminder that notes have built up, or when the same correction keeps coming back. Say "triggers" to also review every revisit condition, or give a question to answer from the notes.
---

# Go through the notes

## When to run

When the owner chooses: after a reminder, after a run of sessions, or when corrections are repeating.
Never from inside a task, never on a timer, and never without the owner present: every lasting change
here is theirs to decide. It works best in a conversation that has done no other work. It needs Vesta
set up in the project and engine 0.1.0 or later.

`$ARGUMENTS` may hold `triggers`, to include the review of every revisit condition, or a question
from the owner to answer from the notes, or nothing.

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
- Report counts with what is behind them (a decision or a proposal by its label, a note by its title),
  never an assurance and never a single health figure.

## What it does

The first part:

1. Window: every note this run reads, with what earlier runs read and what the owner turned down.
2. Counts: which decisions sessions read, and what each said came of it.
3. Trigger review, where asked for: every revisit condition against the project as it stands.
4. Consolidate: decisions that may say the same thing.
5. Group: the notes that share a shape.
6. Route: the cheapest change that would have prevented each group.
7. Draft: a proposal for each group that earned one.

The second part:

8. Gate: every waiting proposal is put to the owner, who decides each.

The third part:

9. Seal: the notes that were read are filed, the ones that wait are kept, and the run is written up.

The sheet lists and numbers the steps it prints: the third is there only where asked for, and a
project's configuration may leave others out.

## Procedure

1. **Find the project root:** the nearest folder at or above the working directory that holds
   `vesta/vesta.yml`. Where there is none, tell the owner to run `/vesta-init` and stop. Below, `vesta`
   stands for `python3 "<that root>/vesta/.engine"`; use `python` where `python3` is not found.
2. **Check the engine.** Run `vesta version`. Where the engine is older than 0.1.0, tell the owner to run
   `/vesta-init upgrade` and stop. Where the command fails because `vesta/.engine` is not there and
   `vesta/.engine.next` is, an upgrade stopped half-way: `/vesta-init upgrade` finishes it. Run `vesta doctor`: where it shows a session not closed, tell the
   owner, and go on only on their word.
3. **Print the first part.** Run `vesta walk learn`. Add `--with trigger-review` where the owner said
   `triggers`. Add `--ask -` where the owner gave a question, and give it on standard input. The engine
   starts a run over the notes open at that moment, or goes on with one left unfinished; a note written
   later waits for the next run.
4. **Carry out the part** from top to bottom. Each section's **Do** line is an instruction for now. Work out what each section found, including nothing, as your own working: the owner is told only what the sheet's last part asks for. Set a note aside with `vesta obs dispose` only where it
   is noise or its subject has left the project. Draft with `vesta propose`, and read each draft back
   with `vesta proposals <id>` until it reports nothing wrong.
5. **Print the second part** with the command the first part ends on. Put every waiting proposal to the
   owner in one message: its label, what would change in a sentence or two, how many notes and sessions
   it rests on, what it would cost from now on, and the case against it. Take a decision on each. On a
   yes that names it, run `vesta apply <id>`; on a no, `vesta reject <id> --reason -` with their reason. What the owner does not decide stays waiting.
6. **Print the third part** with the command the second part ends on, and carry it out: name the notes
   to keep, and run `vesta pass seal --note -` with the few lines the section describes.
7. **Report the run to the owner** once, as the sheet's last lines ask, from what `vesta pass seal` printed.

## Do / Don't

- Do choose the cheapest change that would have prevented the shape. Don't answer every group with a
  new decision: a wider `when` line on an existing decision is cheaper, and nothing is cheaper still.
- Do state a proposed decision at the level of the shape. Don't copy the notes into it: three
  instances under one heading are three notes, not a decision.
- Do treat the counts as pointers. Don't propose retiring a decision because few sessions read it.
- Do propose a change to one of the project's standing questions or checks when the notes show it
  missed, asked too narrowly, or came too late. Don't add a standing question where a check, a `when`
  line or a decision would do.
- Do tell the owner when a shape is better fixed in the project itself, and leave that to them. Vesta
  records; it does not change the project.
- Do merge two decisions that say the same thing, and show the owner two that conflict. Don't treat a
  pair the sheet lists as a duplicate because its words overlap; read both.
- Do keep a note open by name when it waits for a second session. Don't leave the run unsealed.

## What this does not guarantee

Grouping is judgment over prose; a shape split or merged wrongly is caught only when the owner reads
the evidence. A run remembers earlier runs only through the titles and rejection lines its first
section prints. The counts are lower bounds: a miss nobody noticed is in none of them. Nothing runs
this skill if the owner does not, and a pile nobody reads teaches nothing. Nothing verifies that the
sheet was carried out honestly. The engine records that a proposal was applied and cannot tell whether the owner approved it.
