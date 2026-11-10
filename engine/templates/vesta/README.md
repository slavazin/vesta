# Vesta

This folder holds the decisions this project has made, kept so that an AI agent starts each task knowing
them and the same correction is not needed twice. Every lasting change to it is shown to a person first.

## When to use it

| Moment | Type to the agent | What comes back |
|---|---|---|
| starting a task | `/vesta-hook <the task>` | a short brief: what was decided before that bears on this task |
| finishing a task | `/vesta-insight` | a short report, and now and then a proposal to approve or reject |
| when reminded, or when the same corrections keep recurring | `/vesta-learn` | a list of proposals, each to approve or reject |

When shown a proposal, answer yes or no by its number. Nothing else is asked of you.

## Changing how it behaves

Ask the agent in plain words: to be quieter or more proactive, to remind sooner, later or never, to name
decisions differently. Each such change comes back as a proposal to approve.

## What you may want to read

`decisions/` holds the decisions, one file each, readable as they are.

## What it needs and does not do

- It needs Python 3.9 or later.
- It does not run itself: an agent runs it when you type one of the three commands, or when the project's
  agent instructions tell it to.
- It suits a project worked on across many sessions, by one person or by a team in which one person at a
  time approves changes (in a shared repository: on one branch). On a one-off task it is overhead.

`INTERNALS.md` explains how it works. Nothing requires reading it.
