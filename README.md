# Vesta

Vesta keeps what a project has decided as plain text files beside the project, and hands an AI agent the
decisions that bear on a task when the task starts. Every lasting change to those files is shown to a
person, who says yes or no.

It is a set of six agent skills and a small Python program with no dependencies. Everything it knows
about a project lives in one folder, `vesta/`, inside that project.

**Status: experimental.** See *Status* at the end for what is untried.

## When to use it

Three moments, and one habit.

| Moment | Type to the agent | What comes back |
|---|---|---|
| starting a task | `/vesta-hook <the task>` | a short brief: what was decided before that bears on this task |
| finishing a task | `/vesta-insight` | a short report, and now and then a proposal to approve or reject |
| when reminded, or when the same corrections keep recurring | `/vesta-learn` | a list of proposals, each to approve or reject |

The habit: when shown a proposal, answer yes or no by its number. You can stop reading here and use it.

Once, at the start, there is a fourth: `/vesta-backfill` reads conversations you had with the agent
before Vesta was set up, so that it does not begin with nothing. And whenever you want Vesta itself
to behave differently, `/vesta-config` changes it by asking; you never edit a configuration file.

## Who it suits

One person, or a small team in which one person at a time approves changes (in a shared repository:
on one branch), working on one project across many sessions with an agent. It does not suit a one-off
task: there it is overhead. The project need not be software. A folder of reports and letters works the
same way.

Two parts of it need the project's work to be files inside the project folder: finding the decisions
that cover a file, and noticing at the end of a task a decision that should have been read. When it
looks for the files a task changed, it skips folders named `.git`, `node_modules`, `.venv`, `dist` and
`build`; ask the agent to change that list if your work lives in one of them.

## What it needs

- An agent harness that loads skills and can run a script. These instructions are for Claude Code.
- Python 3.9 or later, and nothing else.
  - macOS: `brew install python`, or the installer from python.org.
  - Windows: `winget install Python.Python.3.12`, or the installer from python.org.
  - Linux: the `python3` package of your distribution.

## Install

1. Get a release: download the latest one from this repository's releases page and unpack it, or clone
   the repository and check out its tag. Each release is tagged `v` and the engine's version, `v0.3.0`.
2. Copy the six folders under its `skills/` (`vesta-init`, `vesta-hook`, `vesta-insight`,
   `vesta-learn`, `vesta-backfill`, `vesta-config`) into `.claude/skills/` of your project. From the unpacked repository:
   - macOS and Linux: `mkdir -p "<your project>/.claude/skills" && cp -R skills/vesta-* "<your project>/.claude/skills/"`
   - Windows PowerShell: `New-Item -ItemType Directory -Force "<your project>\.claude\skills"; Copy-Item -Recurse skills\vesta-* "<your project>\.claude\skills\"`

   To have the skills in every project, put your home folder in place of `<your project>`.
3. Open the project in Claude Code, in a new session so that it sees the skills, and type `/vesta-init`.

## How to

### Set it up in a project

Type `/vesta-init`. It confirms the folder with you, asks for a name to record on approvals and for how
much it should ask of you, and creates the `vesta/` folder. It then offers two things you can decline:

- a short block in the project's agent-instruction file (`CLAUDE.md` or `AGENTS.md`), so that the agent
  runs Vesta at the start and end of a task without being told;
- recording up to three things the project has already settled and an agent keeps getting wrong.

It writes nothing outside `vesta/` without asking. Keep `vesta/` with the project: where the project is
under version control, commit it. It carries its own `.gitignore` for working state.

### Start with what earlier conversations taught

Type `/vesta-backfill` after setting up, or later, when tasks were finished without `/vesta-insight`.
It finds the conversations you had with the agent in this project, tells you which folder they are in
and how many there are, and asks before it opens one. It then reads the latest five (say `last 8` for
another number, up to 20) and writes a note for each time you corrected the agent, redirected it, or
said how work is done here. Say `corrections` to keep only the outright corrections.

When two tasks have ended without `/vesta-insight`, the next `/vesta-hook` says so and names this
command. It writes notes and nothing else. To turn them into decisions, type `/vesta-learn` in a new
conversation; you approve or reject each one there.

It knows where Claude Code keeps conversations. For anything else, save a conversation as text and
give the path: `/vesta-backfill notes/session-with-agent.md`. Short quotes of what you said end up in
notes under `vesta/observations/`, which is part of the project. The agent is told to quote nothing
that reads as a password or a key, and nothing checks that it did: you see every note's title in its
report, and the notes are plain files you can read before committing them.

### Start a task

Type `/vesta-hook` followed by the task in your own words. The agent reads the decisions that bear on
it and gives you a brief: which decisions apply and what each asks of this task, and anything waiting
for you. Then it starts the work. If you declined the instruction block, this is the command to
remember; with the block, the agent runs it for you.

### Correct the agent mid-task

Just say it. Your words become a note at the end of the task. You need no command.

By default the agent notes them at once, which takes a moment of the work each time. *Keep Vesta's
own work out of the task*, below, has two ways around that.

### Finish a task

Type `/vesta-insight`, or let the agent run it before it reports the work done. It records which
decisions it used and what you corrected, writes a few short notes, and gives you a short report.
Notes decide nothing by themselves.

### Answer a proposal

A proposal says what would change, why, and what it would cost every later task. Answer yes or no by
its number: "yes to P-003", "no to P-004, we stopped doing that". Only a yes that names the proposal,
given after you saw its text, counts. A no is recorded with your reason, so the same thing is not
proposed again.

### Turn repeated corrections into decisions

Type `/vesta-learn` when reminded, or when you notice yourself giving the same correction again. The
agent reads the notes that have built up, groups the ones that say the same thing, and proposes the
smallest change that would have prevented each group. Often that is a wider description on an existing
decision, sometimes a new decision, often nothing. A note seen only once is kept for next time.

### Record a decision yourself

Tell the agent what was decided and ask it to propose recording it. It comes back as a proposal like
any other. You may also edit a decision file by hand: the next command logs that you did.

### See what it holds

`vesta/decisions/` holds the decisions, one readable file each. `vesta/README.md` is a one-page guide
for whoever opens the folder, and `vesta/INTERNALS.md` explains how it works. From a terminal, in the
project folder:

- `python3 vesta/.engine index` lists every decision with the situations it applies to.
- `python3 vesta/.engine show D-001` prints one in full.
- `python3 vesta/.engine proposals` lists the proposals waiting for you.
- `python3 vesta/.engine check` says whether the folder is in order.
- `python3 vesta/.engine doctor` says what it is running on and what it found.

### Change how it behaves

Type `/vesta-config` and say what you want in plain words: quieter or more proactive, reminders
sooner, later or never, decisions named differently. Type it alone to be told what can be changed and
how each thing stands. A change for the whole project comes back as a proposal to approve. A choice
that is yours alone, such as who notes your corrections, takes effect at once. You never open a
configuration file.

### Keep Vesta's own work out of the task

Some choices are yours and your machine's, not the project's, so they are not in `vesta/vesta.yml`
and need no proposal. `/vesta-config` changes one by asking; `python3 vesta/.engine setting` lists
them, and `python3 vesta/.engine setting <name> <answer>` changes one. They are kept under `vesta/.state/`, which is never
committed, so a colleague's choices are their own.

- `jotting`: who notes your corrections while a task is worked on. `here`, the default: the working
  agent, as it goes. `later`: nobody; your words are read back from the conversation when the task is
  reviewed. `aside`: each time you say something, a copy of the conversation is started, notes a
  correction where there is one, and ends, while the work goes on. Each copy costs about what one
  reply costs.
- `review`: who carries out the first part of `/vesta-insight`, which reads the task back and writes
  notes. `here`, the default: the working agent. `aside`: a copy of the conversation, so the working
  conversation reads only the result and goes on with the part that is put to you.
- `harness`: which program the agent runs in. The engine finds it; choose it only where it finds the
  wrong one.

`later` and `aside` work in Claude Code. In any other harness they fall back to `here`, and
`setting` says so. For `aside`, Claude Code has to be told to run a command each time you say
something: `setting jotting aside` prints the lines to add to `.claude/settings.local.json`. The
start of a task asks which `jotting` you want, until you have answered.

### Upgrade

Delete the `vesta-*` folders under `.claude/skills/`, copy the newer ones there as in *Install*,
and type `/vesta-init upgrade`. Delete first: copying over the old folders leaves old files behind,
and the upgrade then refuses the copy.

The upgrade replaces the shipped files in `vesta/` that you have not changed. A file you have changed
is left as it is, and the new text is written beside it as `<name>.new` for you to merge and then
delete. Your settings in `vesta/vesta.yml` and your decisions are never replaced. If it stops half-way,
typing the same command again finishes it.

### Fix something that looks wrong

Ask the agent to run `check` and `doctor` and tell you what they say; each message names what to do. A
task that ended without `/vesta-insight` leaves a session open, and the next `/vesta-hook` offers to
close it.

### Remove it

Delete the `vesta/` folder, the block between the two `vesta` marker lines in the agent-instruction
file, and the `vesta-*` skill folders. Vesta wrote nothing else.

## The loop

1. At the start of a task the agent reads the decisions that bear on it and tells you which they are.
2. During the task, each time you correct the agent is noted: by the agent as it goes, or, where you
   choose so, read back from the conversation afterwards or noted by a copy of it.
3. At the end, the agent records what it used and what you corrected, as short notes. Where you made a
   real choice between alternatives, it may propose recording it as a decision.
4. Every so often you run `/vesta-learn`. The agent reads the notes that have built up, looks for the
   same thing happening more than once, and proposes the smallest change that would have prevented it.
5. You approve or reject each proposal. Only then does anything lasting change.

## What a decision looks like

One file per decision, readable as it is:

```markdown
---
id: D-004
status: accepted
decided: 2026-03-14
when: >-
  adding or changing a call to an outside service; choosing a timeout or a retry count; a
  request that hangs or fails now and then
why: an unbounded wait in one call stalls the whole job queue
except: calls between this project's own services, which use the internal client
scopes: [src/integrations/, src/http/]
---
# Every call to an outside service sets a timeout of ten seconds or less and retries at most twice

## Context
Jobs run one at a time from a single queue. A call that never returns holds the queue.

## Decision
Every call to an outside service sets a timeout of ten seconds or less and retries at most twice.

## Warrant
- On 2026-03-10 one call with no timeout held the job queue for six hours.
- False if: a service this project depends on needs more than ten seconds for a normal response.
```

The `when` line is how the agent finds it. The `False if` line says what would make it wrong, so that
a later session can tell you when it no longer holds. (A real file carries a few more bookkeeping fields.)

Nothing in it is particular to software. In a folder of reports and letters the same file might hold
"A letter about a late delivery names the new date in its first sentence", found by a `when` line such
as "writing to a client about a delay" and covering `letters/`.

## What a session costs

- **At the start,** the agent reads one short block for each decision, and every open condition for
  revisiting one, and gives you a brief.
- **At the end,** it marks which decisions it used, lists your corrections, answers the project's
  closing questions (four to begin with), and writes a few short notes. That is several commands and a
  few minutes of agent time. There is a short form for a session that changed little.
- **Each decision you add** is one more block read at the start of every task. That is why a proposal
  states its cost, and why most notes never become decisions.

## How much it asks of you

You choose one of three levels when setting up, and can change it by asking:

- `quiet`: a three-line brief, a one-line report, no questions.
- `standard`: the brief and the report; a question only where two decisions conflict or one looks wrong.
- `active`: the agent also asks up to five questions before starting, and at the end puts in front of
  you the choices it made alone.

It reminds you when notes have built up or proposals are waiting. Ask the agent to remind sooner, later
or never; like any lasting change, that comes back as a proposal.

## How much it asks of you

You choose one of three levels when setting up, and can change it by asking:

- `quiet`: a three-line brief, a one-line report, no questions.
- `standard`: the brief and the report; a question only where two decisions conflict or one looks wrong.
- `active`: the agent also asks up to five questions before starting, and at the end puts in front of
  you the choices it made alone.

It reminds you when notes have built up or proposals are waiting. Ask the agent to remind sooner, later
or never; like any lasting change, that comes back as a proposal.

## What it does not do

- It does not run itself. An agent runs it when you type a command, or when the project's agent
  instructions tell it to, and an agent may still skip it.
- It cannot tell whether an agent carried a step out honestly, or whether you really approved what was
  applied. It records that it was.
- Its checks read the shape of the files, never whether a decision is true.
- It does not change your project. It records what was decided; fixing the project stays with you.
- Reading back an earlier conversation reads only the words, not the work, and only where it can find
  or is given the conversation. It never opens one without asking.
- A copy of a conversation started aside is a second agent: it is told to note one thing or carry out
  one sheet and to change nothing else, and nothing but the commands it is allowed holds it to that.
  It runs on the model your harness starts by default.
- It does not search by meaning. A decision is found by its `when` line and by the paths it names.

## Status

Experimental. Its tests pass on Linux, macOS and Windows; these are untried:

- use by people on their own projects, over weeks;
- an agent watched following the skills through a real task (the tests stand in for the agent with
  fixed inputs);
- use by a person on Windows or Linux (only the tests have run there);
- an upgrade between two released versions;
- a team sharing one `vesta/` folder across branches and merges;
- any harness other than Claude Code;
- `jotting` and `review` set to `aside` over a long task: each was run once, on a short conversation;
- reading back conversations kept by a later version of Claude Code than the one it was written
  against: the files' form is not documented.

## For contributors

    python3 tools/build.py
    python3 -m unittest discover engine/tests

Both need Python 3.9 or later and nothing else. `engine/` is the program; `tools/build.py` copies it
into `skills/vesta-init/engine/`, which is the copy a project receives, so run it before the tests
after any change under `engine/`. `skills/` holds the six skills. The tests are under `engine/tests/`.

`python3 tools/neutrality.py` checks that nothing shipped holds a string from a private list of terms
a maintainer keeps outside the repository; without that list it checks nothing and says so.

### Releasing

The version is the `ENGINE` line of `engine/kernel/version.py`; it is what `version` prints in a project
and what an upgrade compares. To release: change that line, run `tools/build.py` and the tests, commit,
and tag the commit with what `python3 tools/release.py` prints. The tag check in CI fails a tag that
names another version.

## License

MIT. See `LICENSE`.
