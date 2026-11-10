A record printed in full above is loaded: read it. Then read every index block against the task:
the paths it touches, the parts of the project it involves, and the kind of work it is. For each block
whose {when} line matches or could plausibly match, run `load <id>` and read the record. Load a doubtful
match: a record that turns out not to apply costs a glance. Don't act on an index block: it says when to
open a record, never what the record decides.

Where two loaded records conflict, show the owner both and don't choose between them. Where a loaded
record does not match the project as it stands, compare the mismatch with the record's `False if:` lines and its {triggers}; then tell the owner what does not match. State the result as a count with the ids behind it, or as
`none matched (index read)`.

[quiet] Ask the owner nothing at this step. Keep what you tell them to what binds this task.

[standard] Ask the owner a question only where two loaded records conflict or one reads false.

[active] Ask the owner a question where two loaded records conflict or one reads false, and where it stays open whether a record applies to this task.
