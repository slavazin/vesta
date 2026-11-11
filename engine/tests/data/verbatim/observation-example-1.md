---
uid: a3f29c0e
id: O-20260314-a3f29c0e
date: 2026-03-14
session: S-20260314-1c0e
source: review
via: lens:friction
anchor: scripts/release.sh
record: ""
recheck: ""
steer-kind: ""
moment: ""
missed-by: ""
disposition: open
held: []
---
# The release script asks for the version number three times

Each of the three stages prompts for the version and none passes it to the next. A mistyped second answer
produced a tag that did not match the changelog.
