# How Vesta works

For whoever wants the mechanism, and for the agent. Using Vesta does not require reading this.

## What is where

| Path | Holds |
|---|---|
| `README.md` | what this folder is and when to use it |
| `INTERNALS.md` | this file |
| `vesta.yml` | the configuration |
| `language.md` | the writing rules and the project's own terms |
| `decisions/` | one file per decision, with a `README.md` and a `SCHEMA.md` |
| `observations/open/` | observations no learn pass has archived |
| `observations/archive/` | observations a learn pass or a decided proposal archived |
| `proposals/` | proposals awaiting the owner, each with its draft where it creates a record |
| `walks/` | the project's own rows and lenses for the start of a task, its close, and the learn pass |
| `log/admissions.md` | one line per decided proposal |
| `log/admitted.json` | the fingerprint of every governed file as last approved |
| `log/consultations.jsonl` | one line per decision a session read in full |
| `log/proposals/` | decided proposals, kept whole |
| `log/passes/` | one note per learn pass |
| `.manifest.json` | the fingerprint of every file as shipped, read on upgrade |
| `.gitignore` | keeps working state out of version control |
| `.engine/` | the engine; replaced on upgrade |
| `.state/` | working state of open sessions; never committed |

## How changes are made

- A lasting change is made through a proposal the owner approves. Running `apply` is the record that
  they did; a name or a reference given with it is bookkeeping.
- The change made first stands. A waiting proposal it leaves unable to be applied is closed as stale, with
  a line in `log/admissions.md` saying what overtook it.
- Observations are written freely and decide nothing.
- A decision is replaced by a successor, never rewritten or annotated.
- Nothing is retired for being quiet. A decision leaves only when its subject has left the project.
- A decision, a walk file or `language.md` may be edited by hand. The next command logs the edit in
  `log/admissions.md` and says so.
- `vesta.yml` and every `SCHEMA.md` are what the engine reads the folder by. One edited by hand is reported
  by `check` as an error until the owner accepts it with `adopt`, and no change is written over it.

- Three keys of `vesta.yml` are the owner's own setup answers and need no proposal until the first
  proposal is decided: `owner`, `engagement` and `pointer-file`, each written by `init`.

## Upgrades

- An upgrade is the one change made without a proposal: the owner asks for it, and one line in
  `log/admissions.md` records it.
- It is run by the new engine from `vesta/.engine.next/`, and never goes back to an older engine or to
  an engine older than the folder.
- A shipped file this project has not changed is replaced with the new text. One it has changed is left
  as it is, and the new text is written beside it as `<name>.new` for the owner to merge and delete.
  `vesta.yml` and the logs are never replaced. A `<name>.new` the owner has not deleted is never
  written over: an upgrade with a newer text for it is refused until it is gone.
- The engine in a project is a copy inside it, whole as it was shipped: a link to a folder elsewhere,
  or a copy that lacks a file or holds one that was not shipped, is not put in place.
- It is refused while `vesta.yml` or a `SCHEMA.md` is changed by hand and not accepted, while another
  hand edit is not logged yet, and where the folder would end with an error `check` does not report now.
- The files change together; the new engine takes the old one's place after that. An upgrade that stops
  between the two is finished by running it again.

## Sessions

- A session is one task's working memory: what was asked, which decisions were read, what was noted. It
  lives under `.state/` until it is closed.
- One session is open at a time. `walk start` refuses to open a second until told which case holds: the
  same conversation has moved on (`--continue`), an earlier conversation left its session open (`--new`),
  or two agents share the checkout (`--parallel`).
- With several sessions open, a command says which it means with `--session <id>`.
- A decision is marked `applied` or `not-applicable` only after it was loaded. One that governed the work
  and was not read is marked `should-have-loaded`.
- Closing a session writes one line per decision it read to `log/consultations.jsonl`. A session left
  unfinished is abandoned, and its lines say `unclosed`.

## Earlier conversations

- `/vesta-backfill` reads conversations held before now, one at a time, and writes notes from what the
  owner said in them. It changes nothing else: the notes wait for a learn pass like any others.
- `history` prints where such conversations are kept and how many files are there. It reads only the
  names and dates of files; `history list`, `history turns` and the `backfill` walk open them. The
  engine reads them and never writes outside `vesta/`.
- The engine knows the files of Claude Code, whose form is not documented and may change. It finds the
  ones kept for the project's own folder; ones kept under another folder's name are read by naming that
  folder or file with `--in <path>`. Any file or folder of saved text is read by the place `file`, also
  with `--in <path>`; there the engine cannot tell the owner's words from the agent's, and the reader does.
  A file with lines of which none is in the form the engine knows does not read; named alone, it is
  read as saved text.
- From a file of Claude Code the owner's words are: what they typed, also while the agent was working;
  the words after a command they typed; what they answered where the agent asked; and what they said on
  turning an action down. What the harness wrote in their place is left out and counted on the sheet.
- Each reading gets a session of its own, opened late. It is no task's session: it takes notes and is
  closed or abandoned, and nothing else; no other command takes it for the open session; no proposal
  names it as its source; and closing it adds no line to `log/consultations.jsonl`.
- What was read back is kept under `.state/`, on this machine only, by what was said and not by the file.
  A conversation read in full is refused a second time, so that its notes are not written twice; one
  that was added to is offered again for what is new; words carried over into a second file are read
  once. A reading whose session was abandoned before any note was written does not count.
  `history forget <place> <conversation>` drops every reading that holds what was said in one, so that
  it is offered again; notes already written from it stay.
- The start of a task says when tasks have ended without a review since the last thing read back
  (`reminders.unreviewed`, on unless the configuration turns it off), and names `/vesta-backfill`.
- A conversation that cannot be read is refused by name. Lines of one that do not read are counted on
  the sheet.
- A project whose `vesta.yml` names no `backfill` walk has the shipped one, with the steps `earlier` and
  `mint`, for as long as `walks/backfill.md` is there. Deleting that file removes the walk.

## Learn passes

- A pass reads the notes that were open when it opened, and no others. One pass is open at a time, and
  `walk learn` goes on with an open one. Its working state lives under `.state/` until it is sealed.
- During a pass, `obs dispose` sets aside a note that is noise or whose subject has left the project. A
  note that is evidence of a waiting proposal is left to that proposal.
- `pass seal` archives as read every note of the pass that is still open, save the ones it is told to keep
  open and the ones a waiting proposal cites, and writes the pass note under `log/passes/`. A note kept
  open three times already is archived unless it is named again.

## Glossary

| Term | Meaning |
|---|---|
| owner | the person who approves lasting changes |
| agent | the AI session doing the work |
| session | one task's worth of agent work, from `/vesta-hook` to `/vesta-insight` |
| pass | one run of `/vesta-learn` |
| window | the observations one pass reads: every observation open when the pass opens |
| store | one folder holding one kind of record under one set of rules |
| ledger | a store whose records are fixed in meaning once written |
| register | a file that states how things stand and is corrected in place |
| record | one entry in a store: one file with a frontmatter block and a body |
| decision | a record of something settled: what was chosen, why, and what would make it wrong |
| observation | a record of one noticing with one anchor; it proposes nothing and binds no one |
| proposal | a drafted lasting change awaiting the owner |
| anchor | a reference a reader can open: a path, a commit, a record label, a link, or the owner's statement by date |
| index | a listing computed from the records each time it is asked for; never stored |
| governed | said of a file that changes only through an approved proposal |
| the `when` line | the line on a record that says when to open it, in the words a task arrives in |
| the `why` line | one line naming what goes wrong if the decision is ignored |
| the `except` line | a case the `when` line's words match that the decision does not cover |
| scope | a folder path the decision governs |
| warrant | what grounds a decision: anchored facts, falsifiers, and what nothing verifies |
| falsifier | an event that would make the decision wrong; a `False if:` line |
| revisit trigger | a condition in the project that means the decision is due another look, with the act owed |
| probe | a condition the engine evaluates by reading the project: `exists`, `missing`, `grep` |
| recheck | a probe on an observation that would mean the noticing matters again |
| successor | the decision that replaces another |
| load | to read a record in full, and have the engine note that the session did |
| latch | any condition that brings a record or a duty to a session's attention at a set moment |
| checkpoint | a set moment at which latches are checked: `start`, `close`, `learn` |
| walk | checking everything that belongs to a checkpoint, in order |
| walk file | the file holding a checkpoint's project-owned rows and lenses |
| row | one project-owned latch in a walk file: a condition, one thing to consult, one act owed |
| lens | a standing question asked at a checkpoint, paired with its counterfactual |
| counterfactual | the challenge paired with a lens that names how its answer goes too far |
| walk sheet | what the engine prints for a checkpoint: each step's data and instruction |
| seed | a row or lens the product ships; the project's own from then on |
| brief | what `/vesta-hook` reports at the start of a task |
| mark | the close's word on a loaded decision: `applied` or `not-applicable` |
| jot | a one-line note captured mid-session and turned into an observation at the close |
| steer | something the owner says that changes what the session would otherwise have done |
| should-have-loaded | a decision that governed the session's work and was not loaded at the start |
| off-map | said of something worth recording that no record, row or lens asked about |
| bundle | what the engine recorded of a session: its tasks, the records loaded, the jots, the paths changed |
| close report | what `/vesta-insight` reports to the owner |
| shape | what several observations have in common once the particular file, task and day are removed |
| group | the observations of one shape |
| bar | the evidence a kind of proposal needs before it is drafted |
| ladder | the ordered list of homes for a shape, cheapest first |
| apply | the engine carrying out an approved proposal |
| disposition | where an observation ended up |
| hold | to keep an observation open across a pass, by name |
| archive | where a pass or a decided proposal puts the observations it has finished with |
| check | a mechanical validation the engine runs |
| residue | what a check does not verify, stated with the check |
| standing cost | what a record, row or lens costs every later session by existing |

## Limits

- Nothing forces a walk to be run, and nothing can tell whether one was carried out honestly.
- The engine records that a proposal was applied and cannot tell whether the owner approved it.
- The checks read shape, never truth.
- Matching by path, the close's search for decisions that should have been read, and probes work only
  where the project's work is in files under the project folder.
