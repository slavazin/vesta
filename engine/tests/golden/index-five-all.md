# Index

## decisions

```
D-001  [reports/, letters/]
  when:   sending anything to a client
  except: internal working notes
  why:    a stale figure goes out

D-002  [src/integrations/, src/http/]
  when:   adding or changing a call to an outside service; choosing a timeout or a retry count; a
          request that hangs or fails now and then; a job that never finishes; a queue that stops draining for no stated reason
  why:    an unbounded wait in one call stalls the whole job queue
  unstable-if (t1): an outside service documents a slower response

D-003  superseded by D-004

D-004
  when:   naming a client in a letter
  why:    a misspelled name reads as carelessness

D-005  retired: the fax line was closed on 2026-01-02
```

Each block says when to open a record, never what it decides. Read a record with `show <id>` before acting on it.

This index does not show: whether a `when` line is written in the words a task arrives in — one that is not will go unrecognized, and nothing here detects that; a record with no paths is never matched mechanically. The close's sweep and the owner's corrections are where such a miss shows.
