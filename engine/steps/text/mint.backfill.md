Read the Fields table of the SCHEMA file named above: it gives the values each key takes and when a
key is filled. Read the *Write card* of {language}. Then send every prepared observation in one call
of the `obs add` command shown above with `--session {session}` added, giving the JSON array on
standard input, one item for each. Leave out a key that does not apply. One noticing, one anchor, no
fix. Don't look at earlier observations to see whether something was noticed before: counting what
recurs is the job of the learn pass. Where the command refuses, nothing was written: correct the items
it names and send the whole array again. Where nothing was prepared, send nothing.

Then run `session close --session {session}`.
