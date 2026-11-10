Put each choice listed here through the test printed above, in order. A choice that fails any part
stays an observation, and nothing more is done with it.

For a choice that passes: where a record in force already covers the situation, propose a change to
that record with `propose latch-edit --target <id>` or `propose supersede --target <id>`, or propose
nothing. Otherwise run `propose add --target {store} --evidence <that observation> --source {session}`,
fill the proposal and its draft under the store's SCHEMA.md and `vesta/language.md`, and run
`proposals <id>`: read the note it prints on records that may already cover the draft, and correct
what it says is wrong. This is the one case where a single observation is enough for a new record:
the owner has already decided it.
