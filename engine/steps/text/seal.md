Name the notes to keep open for a later pass, each with what it waits for. A note that is evidence of
a waiting proposal is kept open without being named. One kept open three times already is archived
unless the owner says otherwise; ask them about each such note.

Then run `pass seal --note -` and give these lines on standard input: one for each of {keys}, and one
`{waiting} <id>: <what it waits for>` line for each note to keep open. `Groups:` and `Ungrouped:`
are the counts from the Group section; `Not done:` names anything this pass skipped, or says
`nothing`; `Consolidation:` says what was done about the pairs, where there were any. `--hold
<id>,<id>` keeps notes open too, with no reason recorded.

Every other note still open is archived as read by {pass}, and the pass ends.
