# Proposals

This folder holds proposals awaiting the owner: each is one drafted lasting change. A proposal that would
create a record has that record's full text beside it, in `<label>.draft.md`.

It is a register: a pending proposal may be edited in place until it is decided.

**Who reads it.** The owner, when a session closes or a learn pass runs. Each start of a task lists what
is waiting.

**How a proposal enters.** A session or a learn pass drafts it with the engine's `propose` command.

**How a proposal leaves.** The owner approves or rejects it by its label. The engine then carries out an
approved change, fills the proposal's `outcome`, and moves the proposal and its draft to `log/proposals/`,
where they stay. An undecided proposal stays here.

`SCHEMA.md` says how to write one.
