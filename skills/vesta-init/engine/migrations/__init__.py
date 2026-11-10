"""Migrations: one module for each step of the folder's schema, `m<from>_<to>.py`, with one function
`migrate(tree)`. A migration changes structure only; it never rewrites what a record says. It
writes through the tree it is given and nowhere else. `upgrade` runs the steps in order, then writes
the new `schema:` number, records the fingerprints of what changed, and refuses the whole upgrade
where the folder would end with an error it does not have now. The command line finds each by its
name (cli/manifest.py)."""
