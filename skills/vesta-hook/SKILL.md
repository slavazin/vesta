---
name: vesta-hook
description: Start a task with what this project has already decided. Reads the project's recorded decisions, finds the ones that bear on the task, and gives a short brief before work begins. Use at the start of a task, and again when the work moves to a task the first brief did not cover.
---

# Start a task with the project's decisions

## When to run

At the start of a task. Again in the same conversation when the work moves to a task the first brief
did not cover. It needs Vesta set up in the project and engine 0.1.0 or later.

The task is `$ARGUMENTS`. Where that is empty, use the owner's current request; where there is none,
ask what the session is for.

## Rules that hold throughout

- Change what is under `vesta/` through the engine's commands. Never edit a `SCHEMA.md` or `vesta.yml` by hand.
- Tell the owner about Vesta in plain words: decision, note, proposal, approve, reject. Name a decision
  by its label and title. Leave out the words the sheet uses for its own parts.
- Where a command prints a line that opens `Note:`, tell the owner what it says, in plain words. Name a file by
  its path.
- Report counts with what is behind them, never an assurance: a decision or a proposal by its label,
  a note by its title. "Two decisions apply: D-004 and D-009" is
  a report. "The relevant decisions were checked" is not.

## What it does

1. Recall: the decisions the task's paths reach are read in full; the rest are shown as short blocks to
   match against the task.
2. Triggers: the conditions that reopen a decision are read against the project.
3. Rows: the project's own standing checks for the start of a task.
4. Lenses: the project's own questions about the task.
5. Notices: what is waiting for the owner.

Then the brief, then the work.

## Procedure

1. **Find the project root:** the nearest folder at or above the working directory that holds
   `vesta/vesta.yml`. Where there is none, tell the owner to run `/vesta-init` and stop. Below, `vesta`
   stands for `python3 "<that root>/vesta/.engine"`; use `python` where `python3` is not found.
2. **Check the engine.** Run `vesta version`. Where the engine is older than 0.1.0, tell the owner to run
   `/vesta-init upgrade` and stop. Where the command fails because `vesta/.engine` is not there and
   `vesta/.engine.next` is, an upgrade stopped half-way: `/vesta-init upgrade` finishes it.
3. **Open the session.** List the paths and folders the task will touch, as far as the request and a
   quick look show them. Run `vesta walk start --ask - --paths <those paths>` and give the task, in the
   owner's words, on standard input.
   - Where this conversation already ran `/vesta-hook`, add `--continue`.
   - Where the command refuses because an earlier conversation left a session open: tell the owner. Run
     `vesta walk close --short --session <that id>` and carry it out from what that sheet prints alone.
     Then run the start command again with `--new`.
4. **Carry out the sheet** from top to bottom. Each section's **Do** line is an instruction for now. Work out what each section found, including nothing, as your own working: the owner is told only what the sheet's last part asks for.
5. **Give the owner the brief** the sheet ends with, in its order, and nothing else.
6. **Work.** At the moment the owner corrects or redirects the work, run `vesta jot --steer -` with their
   words on standard input. For anything else worth a line, run `vesta jot -`. A jot takes seconds; don't
   stop to analyse it.
7. **Before telling the owner the work is done,** run `/vesta-insight`.

## Do / Don't

- Do load every decision whose block could plausibly match the task. Don't act on a block: it says when
  to open a decision, never what was decided.
- Do tell the owner when a decision reads false against the project. Don't quietly follow it, and don't
  quietly ignore it.
- Do keep the brief to what binds this task. Don't paste decisions into it: they are already read.
- Don't open `vesta/observations/`, and don't run `obs list`.

## What this does not guarantee

A decision written in words this task did not arrive in is not found here. A decision that names no
paths is found only by reading its block. The end-of-task review and the owner's corrections are where
such a miss shows. Nothing forces this skill to be run. Nothing verifies that the sheet was carried out
honestly. The engine records that a proposal was applied and cannot tell whether the owner approved it.
