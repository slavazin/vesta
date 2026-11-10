---
uid: 2b9e41c7
id: D-002
status: accepted
decided: 2026-02-03
approved-by: A. Reviewer
when: >-
  quoting a figure, a date or a name in anything sent outside the team; preparing a report,
  a letter or a summary for a client
why: a figure copied from an earlier draft goes out after the source has changed
except: internal working notes, which may carry provisional figures marked as such
scopes: [reports/, letters/]
triggers:
  - id: t1
    if: the source sheet moves or is replaced by another system
    then: re-derive where figures are checked against
    probe: missing data/figures.csv
    resolved: ""
supersedes: ""
superseded-by: ""
retired-because: ""
related: []
---
# Every figure sent outside the team is checked against the source sheet on the day it is sent

## Context
Reports are drafted over several days while the source sheet keeps changing.

## Decision
Every figure, date and name in a document sent outside the team is checked against the source sheet on
the day of sending, and the document records that date.

## Warrant
- On 2026-01-28 a quarterly summary went out with two figures from a draft a week old (`reports/2026-q4/notes.md`).
- False if: the source sheet is frozen before drafting starts, so that drafts cannot go stale.
- Not checked: nothing verifies that the check was made; the recorded date is the only trace.
