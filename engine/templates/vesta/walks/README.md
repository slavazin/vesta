# Walks

The files here hold this project's own additions to each walk: `start.md` for the start of a task,
`close.md` for its end, `learn.md` for the learn pass, `backfill.md` for reading back an earlier conversation. The engine's own steps are not listed in them.

A **row** is one check at a fixed moment: a condition, one thing to open, one act owed. A **lens** is a
standing question asked at a walk, paired with a challenge to its answer.

## Row columns

| Column | Rule |
|---|---|
| `id` | `<walk>-NN`, as `start-01`; the engine assigns it |
| `fires-when` | the condition, in the words of the work as it arrives |
| `fires-on` | optional path globs, comma-separated, each in backticks; `—` where the agent judges |
| `consult` | exactly one thing to open: a path in backticks, or a short description of an outside source |
| `owed act` | one bounded act; no two rows owe the same act — merge them instead |
| `level` | `quiet`, `standard` or `active`: the lowest engagement level at which the row is used |
| `origin` | `seed`, or the proposal that added or last changed it |

## Lens columns

| Column | Rule |
|---|---|
| `lens` | a short name in lower case with hyphens; unique across these files |
| `angle` | the question, addressed to the agent, answerable from the session's own work |
| `counterfactual` | the challenge that names how an answer goes too far |
| `level` | the lowest engagement level at which the lens is asked |
| `origin` | `seed`, or the proposal that added or last changed it |

## How these files change

- A row or lens changes only through a proposal the owner approves. Don't edit a table by hand.
- A seed row or lens is the project's own from the first day, and may be changed or removed like any other.
- A row is kept while the thing it consults exists and the situation still occurs. It is never dropped for
  firing rarely.
- A row tells an agent to open something and do something. Read a proposed row as closely as any other
  instruction given to an agent.
