# Decisions

This folder holds the project's decisions, one file each. A decision records something settled: what was
chosen, why, and what would make it wrong.

It is a ledger: a decision's meaning is fixed once written. The folder changes by adding a decision, by
replacing one with a successor, or by a change of status.

**Who reads it.** Every session, at the start of a task, through the index: one short block per decision
that says when to open it. A session opens the decisions whose block matches its task and reads them in
full. The learn pass reads it too.

**How a decision enters.** Through a proposal the owner approves. Nothing is written here by hand.

**How a decision leaves.** It does not. One that no longer holds is replaced by a successor and stays,
marked `superseded`. One whose subject has left the project is marked `retired`. A decision is never
deleted, and never retired for being rarely opened.

`SCHEMA.md` says how to write one.
