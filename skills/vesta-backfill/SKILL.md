---
name: vesta-backfill
description: Read back conversations held before Vesta was in use, or held without it, and write notes of where the owner corrected or directed the work. Gives a new setup something to learn from on its first day. Use right after /vesta-init, or when several tasks were finished without /vesta-insight. Say "last 8" for how many conversations, "corrections" to keep only outright corrections, or give the path of a saved conversation.
---

# Read back earlier conversations

## When to run

When the owner asks: after `/vesta-init`, or later, when tasks were finished without `/vesta-insight`.
Never from inside a task. It needs Vesta set up in the project and engine 0.3.0 or later.

`$ARGUMENTS` may hold any of these, in any order, or nothing:

- `last <n>`: how many conversations to read, from 1 to 20.
- `corrections`: keep only where the owner said the work was wrong. Without it, every time the owner
  corrected the work, redirected it, or said how work is to be done here is kept.
- a path: a file, or a folder of files, holding conversations the owner saved as text.

What the arguments leave open is asked of the owner, one question at a time. Never settle one of these by guessing.

## Rules that hold throughout

- This skill writes notes and nothing else. Draft no proposal, run no `apply`, and write no decision:
  what becomes of a note is decided in `/vesta-learn`, by the owner.
- Open no conversation before the owner has said yes in step 5.
- Write each note as the sheet's last section prints: it holds the rules for a note's title and body,
  the same ones a task's review is held to.
- Tell the owner about Vesta in plain words: decision, note, proposal, approve, reject. Name a note by
  its title. Leave out the words the sheet uses for its own parts.
- Where a command prints a line that opens `Note:`, tell the owner what it says, in plain words. Name a
  file by its path.

## What it does

1. Finds the project and checks the engine.
2. Settles where earlier conversations are read from.
3. Settles how many to read.
4. Settles what to keep: every steer, or corrections only.
5. Asks the owner before any is opened.
6. Lists them, and reads each one into notes.
7. Reports, and says what to do next.

## Procedure

1. **Find the project root:** the nearest folder at or above the working directory that holds
   `vesta/vesta.yml`. Where there is none, tell the owner to run `/vesta-init` and stop. Below, `vesta`
   stands for `python3 "<that root>/vesta/.engine"`; use `python` where `python3` is not found. Run
   `vesta version`. Where the engine is older than 0.3.0, tell the owner to run `/vesta-init upgrade`
   and stop.
2. **Settle where to read from.** Run `vesta history where`, adding `--in "<that path>"` where a path
   was given. It opens and lists nothing: it prints what to ask the owner and what to run next, for
   the harness you are running in and no other. Do what it prints. Where it ends with no place to
   read from, stop.
3. **Settle how many.** Where `last <n>` was not given, ask how many of the latest to read: 5 unless
   the owner says otherwise, 20 at the most in one run. Some files hold nothing; step 6 shows what
   there is.
4. **Settle what to keep.** Where `corrections` was not given, ask: every time the owner corrected the
   work, redirected it or said how work is done here, which is the usual choice; or only where they
   said the work was wrong.
5. **Ask before opening anything, in one message.** Say: the folder or file that will be read, and
   that it is outside the project where it is; how many conversations at the most, and that the engine
   opens files, newest first, until it has found that many; that each is then read by you, as
   anything you read is; and that short quotes of the
   owner's words go into notes under `vesta/observations/`, which is part of the project and is
   committed with it. Nothing checks a quote for a secret: the notes are plain files the owner can read
   before committing. Wait for a yes. On a no, stop; nothing was opened.
6. **List them, then read each.** Run `vesta history list <place> --last <n>`. It lists, newest
   first, the ones that hold something not yet read back, and says what it could not read, passed
   over, left out, or found left open by an earlier run; tell the owner that. Where it lists none,
   say so and stop. Where it does not say that it left out the conversation you are in now, leave
   that one out yourself: the newest, where it opens with the words this conversation began with.
   Show the owner the rest, each in a line with its date and how it opens, and leave out any they name.
   Then, from the bottom of the list up, so that the oldest is read first, for each: run
   `vesta walk backfill --source <place> --conversation <name>`, adding `--corrections` where step 4
   settled on corrections only, and carry out the sheet from top to bottom. Each section's **Do** line
   is an instruction for now. Print the later pieces of a long conversation as the sheet says before
   preparing a note. The sheet ends by closing the session it opened. Where the command refuses, keep
   what it says for the report and go on to the next.
   Where this harness can hand a piece of work to a helper that starts with nothing else in view, give
   each conversation to one, with this step and the command. Otherwise read them in turn.
7. **Report once, after the last.** For each conversation, a line: its date, and the notes written from
   it by title, or that it held nothing to keep, or why it was not read. Then the total. Then say that
   nothing has changed for good: the notes wait, and `/vesta-learn`, run in a new conversation, groups
   them and puts each lasting change to the owner.

## Do / Don't

- Do keep a correction that would hold for the next task. Don't keep one that ordered only that task:
  "rename this file" teaches nothing; "we never rename public files" does.
- Do leave a correction out where the words before it don't show what was being corrected. Don't
  rebuild the work from guesses: only the words are in view.
- Don't look at earlier notes to see whether something recurs, and don't merge two notes from two
  conversations: counting what recurs is the job of `/vesta-learn`.
- Don't read a conversation twice. The engine refuses one that was read back; take the refusal. Where
  the owner asks for one to be read again, `vesta history forget <place> <name>` has it offered again;
  tell them first that its earlier notes stay, so the same thing may be noted twice.
- Don't offer more than the owner asked for: every note is read again in `/vesta-learn`.

## What this does not guarantee

Only the words are read, not the work: a correction made by editing a file, or given in another tool,
is not there. The engine finds only conversations started in the project's own folder; others are read
only where the owner names their folder. The files of
Claude Code are read as they are today and their form may change; a file with nothing in the form the
engine knows is refused by name and never guessed at. In saved text the engine cannot tell the owner's words from the
agent's; the reader does, and may be wrong. Which conversations were read back is kept on this machine
only, so a second machine may read the same one again. Nothing verifies that the sheet was carried out
honestly, and a note written from a misread correction looks like any other until the owner reads it.
