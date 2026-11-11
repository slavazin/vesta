---
name: vesta-config
description: Change how Vesta behaves by asking, without opening a configuration file. Shows what can be changed and what each choice does, changes this machine's own settings at once, and drafts a change for the whole project as a proposal for the owner to approve. Use when the owner asks for Vesta to be quieter or more active, to remind sooner, later or never, to name decisions differently, or asks who notes their corrections. Say what to change, or nothing to see what can be.
---

# Change how Vesta behaves

## When to run

When the owner asks for Vesta itself to behave differently, or asks what can be changed. Not for a
decision about the project's work: that is recorded through `/vesta-insight` or `/vesta-learn`. It
needs Vesta set up in the project and engine 0.3.0 or later.

`$ARGUMENTS` is what the owner wants changed, in their words, or nothing.

## Rules that hold throughout

- Never edit `vesta/vesta.yml`, or any file under `vesta/.state/`, by hand. Every change here is made by
  a command.
- A change for the whole project is a proposal. Run `apply` only for a proposal the owner has approved
  by its id in this conversation, after seeing what it would change. "Looks good", silence, and an
  approval given before the proposal was shown are not approval.
- A setting of this machine is the owner's own and needs no proposal. Change one only where the owner
  asked for it.
- Never settle by guessing which thing the owner means, or which value. Ask.
- Tell the owner about Vesta in plain words: decision, note, proposal, approve, reject. Say what a
  choice does, not what its key is called, unless the owner asks.
- Where a command prints a line that opens `Note:`, tell the owner what it says, in plain words.

## What it does

1. Finds the project and checks the engine.
2. Reads what can be changed, and how each thing stands.
3. Settles which one the owner means, and its new value.
4. Changes a setting of this machine at once; drafts a change for the project as a proposal.
5. Puts the proposal to the owner, and applies or rejects it on their word.
6. Says what holds now.

## Procedure

1. **Find the project root:** the nearest folder at or above the working directory that holds
   `vesta/vesta.yml`. Where there is none, tell the owner to run `/vesta-init` and stop. Below, `vesta`
   stands for `python3 "<that root>/vesta/.engine"`; use `python` where `python3` is not found. Run
   `vesta version`. Where the engine is older than 0.3.0, tell the owner to run `/vesta-init upgrade`
   and stop.
2. **Read what can be changed.** Run `vesta config`. It lists, under two headings, what is this
   machine's own and what holds for the whole project, each with what it does, how it stands now, and
   the values it takes.
3. **Settle which one, and its value.**
   - Nothing was asked for: tell the owner, in a few plain lines grouped by what they affect, what can
     be changed and how each stands, and ask what they want. Leave out what the owner would not
     recognise; name it only if they ask for more.
   - Something was asked for: match it to one line of the list. "Quieter", "fewer questions", "stop
     reminding me", "remind me sooner", "name decisions DEC-001", "don't note my corrections as we go"
     each have one. Where the words fit two lines, or none, say which ones you see and ask.
   - For a setting of this machine, run `vesta setting <name>` and tell the owner what each answer
     does and which can work here, before they choose.
   - Where the value is a number or a name the owner did not give, ask for it.
4. **Make the change.**
   - A setting of this machine: run `vesta setting <name> <answer>`. Tell the owner what it printed:
     what is in effect, why where that is not what they chose, and anything it leaves for them to do.
     Where it prints lines to add to a file, show them whole, with the file's name.
   - Something for the project: run `vesta config set <key> <value>`. It checks the value and drafts a
     proposal with nothing left to fill. Where it refuses, tell the owner why, in its words, and ask
     again. Where it says the value is already so, say that and stop.
   - Something the list does not hold: say so. `vesta config` ends by naming the command that drafts a
     change to any other key by hand; offer that only where the owner asks for it, fill the proposal
     as `vesta/proposals/SCHEMA.md` says, and check it with `vesta proposals <id>`.
5. **Put the proposal to the owner** in one or two plain sentences: what would change, that it changes
   for everyone who works in the project, and its id. On a yes that names it, run `vesta apply <id>`;
   on a no, `vesta reject <id> --reason -` with their reason on standard input. What the owner does
   not decide stays waiting, and the next start of a task lists it.
6. **Say what holds now,** in one or two sentences, and from when: a setting of this machine at once;
   a change for the project from the next command.

## Do / Don't

- Do change one thing at a time, each with its own proposal. Don't bundle two changes the owner might
  answer differently.
- Do say what a choice costs where the list says so: a label that is changed renames every record of
  its kind; a step left out of a walk is no longer carried out.
- Don't turn a reminder off because it was a nuisance once: say that it can be made rarer, and ask.
- Don't offer a setting of this machine that the list says cannot work here without saying that it
  would fall back, and to what.
- Don't use this to record how the project's work is done. "Always run the linter" is a decision, not
  configuration.

## What this does not guarantee

The list holds the choices most often asked for, not every key of the configuration. The engine
checks that a value is of the right kind and that the configuration still reads; it cannot tell
whether the change is wise. A setting of this machine is kept on this machine only: a colleague, or
this owner on another machine, has their own. Nothing forces this skill to be used: a person can
still edit the file by hand, and the engine then records the edit as one made outside a proposal. The
engine records that a proposal was applied and cannot tell whether the owner approved it.
