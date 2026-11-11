Write every prepared observation as the sections printed above say: its title, its body, and what it
leaves out. Go over each one against them before sending it, and rewrite one that states a fix, gives
an instruction, or leans on this conversation to be understood. Read the Fields table of the SCHEMA
file named above for the values each key takes and when a key is filled.

Then send every prepared observation in one call of the `obs add` command shown above{added}, giving
the JSON array on standard input, one item for each. Leave out a key that does not apply.{jots} Don't look at earlier observations to see whether something was noticed
before: counting what recurs is the job of the learn pass. Where the command refuses, nothing was
written: correct the items it names and send the whole array again. Where nothing was prepared, send
nothing.

Then run `session close{option}`.
