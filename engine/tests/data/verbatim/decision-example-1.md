---
uid: 7f3a9c2e
id: D-004
status: accepted
decided: 2026-03-14
approved-by: A. Reviewer
when: >-
  adding or changing a call to an outside service; choosing a timeout or a retry count; a
  request that hangs or fails now and then
why: an unbounded wait in one call stalls the whole job queue
except: calls between this project's own services, which use the internal client
scopes: [src/integrations/, src/http/]
triggers:
  - id: t1
    if: an outside service used here documents a response time above the timeout
    then: re-decide the timeout for that service
    probe: ""
    resolved: ""
supersedes: ""
superseded-by: ""
retired-because: ""
related: []
---
# Every call to an outside service sets a timeout of ten seconds or less and retries at most twice

## Context
Jobs run one at a time from a single queue. A call that never returns holds the queue.

## Options considered
- No timeout, rely on the service: rejected; one stalled call on 2026-03-10 held the queue for six hours.
- A timeout per service, tuned: rejected for now; nothing shows the services differ enough to pay for it.

## Decision
Every call to an outside service sets a timeout of ten seconds or less and retries at most twice.

## Warrant
- On 2026-03-10 one call with no timeout held the job queue for six hours (`docs/incidents/2026-03-10.md`).
- False if: a service this project depends on needs more than ten seconds for a normal response.
- Not checked: nothing verifies that each call sets a timeout.
