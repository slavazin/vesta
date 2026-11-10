---
name: vesta-init
description: Set up Vesta in a project, once. Creates the vesta/ folder that keeps the project's decisions, so that an agent starts each task knowing them. Use when the user asks to set up, install or start using Vesta in a project.
---

# Set up Vesta in this project

## When to run

Once per project, when the owner asks for Vesta to be set up; and with `upgrade`, to replace the
engine with the one this skill carries. It needs Python 3.9 or later.

## Rules that hold throughout

- Write nothing in the project before step 4, and nothing outside `vesta/` at any step, except the block
  of step 6 with the owner's consent.
- After step 4, change what is under `vesta/` through the engine's commands. A proposal that is still
  waiting and its draft are filled and corrected in place.
- Tell the owner about Vesta in plain words: decision, note, proposal, approve, reject. Leave out how it
  works unless they ask.
- Where a command prints a line that opens `Note:`, tell the owner what it says, in plain words.

## What it does

1. Finds the project root and confirms it.
2. Stops if Vesta is already set up.
3. Checks for Python.
4. Copies the engine into the project and creates the `vesta/` folder.
5. Asks the owner for a name to record on approvals, and how proactive Vesta should be.
6. Offers to add a short block to the project's agent-instruction file.
7. Offers to record up to three things the project has already settled.
8. Checks the result.
9. Tells the owner the three moments to use it.

## Procedure

1. **Find the project root.** It is the working directory, or the repository root where the working
   directory is inside a git repository. Tell the owner the folder in one line and wait for a yes.
2. **Stop if it is set up.** If `<root>/vesta/vesta.yml` exists, say Vesta is already set up here, offer
   the upgrade below, and stop.
   The one exception: where the owner says the setup was cut short before step 5 or 6, go on from that
   step.
3. **Check for Python.** Run `python3 --version`; where that fails, `python --version`. Below 3.9, or
   missing: say that Vesta needs Python 3.9 or later and stop. Use the command that worked wherever these
   steps say `python3`.
4. **Copy the engine and create the folder.** Create `<root>/vesta/`, then copy the `engine/` folder
   beside this file (in Claude Code, `${CLAUDE_SKILL_DIR}/engine`) to `<root>/vesta/.engine`, so that
   `<root>/vesta/.engine/__main__.py` exists. Then run `python3 "<root>/vesta/.engine" init`. In the
   steps below, `vesta` stands for `python3 "<root>/vesta/.engine"`.
5. **Ask two things, in one message.**
   - The name to record when they approve a change. An empty answer is fine: the name is for
     the record only.
   - How proactive Vesta should be. `quiet`: a three-line brief at the start, a one-line report at the
     end, no questions. `standard`: the brief and the report, and questions only where two decisions
     conflict or one looks wrong. `active`: as standard, and the agent also asks up to five questions
     before work starts and puts choices it made alone in front of the owner at the end. Use `standard`
     where they have no view.

   Record the answers: `vesta init --owner - --engagement <level>`, giving the name on standard input.
6. **Offer the block.** Find the project's agent-instruction file: `CLAUDE.md` or `AGENTS.md` at the
   root, or the file this harness reads; where both exist, the one the harness reads. Show the owner the
   text of `<root>/vesta/.engine/templates/pointer-block.md` and ask whether to add it.
   - Yes: append the block exactly as shipped, with its two marker lines, to that file, starting on a
     new line. Where the file already holds the two marker lines, replace what is between them and
     don't add a second block. Where no such file exists, offer to create `AGENTS.md` holding only the
     block. Then run `vesta init --pointer-file <path from the root>`.
   - No: change nothing, and tell the owner they run the three commands of step 9 by hand.
7. **Offer the first decisions.** Ask the owner to name up to three things already settled in this
   project that an agent keeps getting wrong or keeps asking about. Zero is a fine answer. For each one
   they name: run `vesta propose add --target decisions --source init`, fill the two files it names
   from the owner's words, run `vesta proposals <id>` and correct what it reports, then put it to the
   owner in one or two plain sentences: what would be recorded, and that the agent would read one short
   block more at every start. On a yes that names the proposal, run
   `vesta apply <id>`; on a no, `vesta reject <id> --reason -`.
   Run `apply` only for a proposal the owner has approved by its id in this conversation, after seeing
   its text. "Looks good", silence, an approval of a different proposal, and an approval given before the
   proposal was shown are not approval. Running `apply` is the record that the owner approved; `--ref`
   may add a commit or a note to it. Make every lasting change through a proposal. A file under `vesta/`
   that the owner edits by hand is logged by the engine; never edit a `SCHEMA.md` or `vesta.yml` by hand.
8. **Check.** Run `vesta check` and `vesta doctor`. Report the errors and warnings as counts, and say
   in plain words what each error is about. A clean result is "0 errors".
9. **Tell the owner what they need, and no more.**
   - `/vesta-hook <the task>` when starting a task; `/vesta-insight` when finishing one; `/vesta-learn`
     when reminded.
   - A proposal is answered yes or no by its number.
   - They can ask at any time for Vesta to be quieter, more proactive, or to remind differently.
   - `vesta/` is part of the project: commit it where the project is under version control.
   - What a session costs: at the start, the agent reads one short block per decision and reports a
     brief; at the end, it notes what it used and what was corrected, in a few minutes of agent time.

## Upgrade

Where `$ARGUMENTS` holds `upgrade`, or another Vesta skill said the engine is too old, do only this:

1. Find the project root as the other skills do: the nearest folder holding `vesta/vesta.yml`.
2. Where `<root>/vesta/.engine` is missing and `<root>/vesta/.engine.next` is there, an earlier upgrade
   stopped half-way: leave that folder as it is. Otherwise remove any `<root>/vesta/.engine.next` and copy
   the `engine/` folder beside this file there. Then run `python3 "<root>/vesta/.engine.next" upgrade`.
   Where it refuses, nothing was changed: tell the owner what it says, do what it names, run it again.
3. Tell the owner what it printed, line by line in plain words, naming each file by its path. A file
   the project had changed is left, with the new text beside it as `<name>.new` for the owner to merge
   and then delete. After the owner merges one into a `SCHEMA.md`, run `vesta adopt <that path>`.
4. Where it says the block in the agent-instruction file is the earlier version's, show the owner the
   new text and, on a yes, replace the block between its two marker lines.
5. Run `vesta check` and report the counts, and in plain words what each error is about.

## Do / Don't

- Do leave every project file untouched except the agent-instruction file, with consent. Don't add Vesta
  instructions anywhere but that block.
- Do take the owner's answers as given. Don't choose a level or a name for them beyond the stated default.
- Don't fill `vesta/decisions/` from the project's documents or code: a decision nobody asked for costs
  every later task a read.

## What this does not guarantee

Nothing forces an agent to run Vesta at the start or end of a task; the block of step 6 asks it to, and
an agent may still skip it. Nothing verifies that an agent carried a step out honestly. The engine records that a proposal was applied and cannot tell whether the owner approved it. The engine checks the shape of the files it created, not that the project
suits Vesta.
