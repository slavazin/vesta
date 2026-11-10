Read each `if` against the project as it stands. Read all of them: a trigger can fire on work that its
record's {when} line does not name. For each `if` that holds, and each whose probe state is `fired`:
run `load <record id> --by trigger`, do the work in the light of that record, and tell the owner which
condition was met. Don't work around a fired trigger. A probe state that opens `error` means the engine
could not evaluate the probe: judge that `if` yourself, and tell the owner that this condition could not be checked automatically and was judged by reading.
