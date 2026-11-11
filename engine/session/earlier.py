"""How the `backfill` walk opens: in a session of its own for what is new in one conversation held before now."""
from __future__ import annotations

from kernel.errors import Refusal, UsageError
from model.abstractions import Opening
from session import harness, history, state

CORRECTIONS = "corrections"


class EarlierOpening(Opening):
    flags = ("--" + CORRECTIONS,)
    options = ("--source", "--conversation", history.PATH_OPTION)

    def open(self, context, options):
        name, source, ref, given = options.get("session"), options.get("source"), options.get("conversation"), options.get("in")
        if given == "":
            raise UsageError("`%s` was given no path" % history.PATH_OPTION)
        given = given or ""
        if name:
            session = state.current(context.tree, name)
            if session.origin is None:
                raise Refusal("%s was not opened to read back an earlier conversation, so this walk has nothing to print for it." % session.id, history.RULE)
            if session.status != state.OPEN:
                raise Refusal("%s is %s: what it read back is done with, and it takes no further note. Nothing was printed." % (session.id, session.status), history.RULE)
            return session, ["It was already open: opened %s." % session.opened] + self._kept(session, options)
        if not source or not ref:
            raise UsageError(
                "this walk reads one earlier conversation: name it as `--source <place> --conversation <name>`. "
                "`history` prints the places and `history list <place>` the conversations"
            )
        found = history.member(context, source, given)
        conversation = history.find(found, ref)
        running = harness.current(context)
        if running is not None and running.history == found.id and not given and running.conversation() == conversation.ref:
            raise Refusal("`%s` is the conversation this command was started from: it is still being held, and it is read at its own "
                          "review, by `/vesta-insight`. Nothing was opened." % conversation.ref, history.RULE)
        mark = history.key(found, conversation)
        with history.lock(context.tree) as held:
            if not held:
                raise UsageError("another command is opening an earlier conversation at this moment; nothing was opened. Run this command again.")
            readings = history.read(context.tree)
            session = history.being_read(context.tree, readings, mark)
            if session is not None:
                return session, ["A session was already open for this conversation: opened %s." % session.opened] + self._kept(session, options)
            turns = history.said(found, conversation)
            mine = history.mine(turns)
            if not mine:
                raise Refusal("that conversation holds nothing %s, so there is nothing to read back. Nothing was opened."
                              % ("the owner said" if any(turn.who for turn in turns) else "to read"), history.RULE)
            done = history.marks_read(context.tree, readings)
            fresh = [turn.mark for turn in mine if turn.mark not in done]
            if not fresh:
                last = history.last_read(context.tree, readings, mark)
                raise Refusal(
                    "everything the owner said in that conversation was read back before%s, and nothing was added to it since; "
                    "reading it again would write its notes twice. Nothing was opened. `history forget %s %s%s` has it offered again."
                    % (", on %s in %s" % (last.get("at", "an earlier day"), last["session"]) if last else ", or is being read now, in another conversation that holds the same words",
                       found.id, history.quoted(conversation.ref), " %s %s" % (history.PATH_OPTION, history.quoted(given)) if given else ""),
                    history.RULE,
                )
            pieces = history.pieces(turns, set(fresh))
            day = history.dated(conversation, pieces)
            ask = "An earlier conversation of %s, which opens: %s" % (day or "a day not known", history.first_words(history.pieces(turns)))
            origin = {"history": found.id, "conversation": conversation.ref, "in": given, "dated": day, "marks": fresh,
                      "only": CORRECTIONS if options.get(CORRECTIONS) else ""}
            session = state.create(context, ask, late=True, origin=origin)
            until = max([turn.at for turn in mine if turn.at] or [conversation.dated])
            history.record(context.tree, readings, mark, session, context.clock.today(), fresh, until)
        said = ["%s was opened to hold what is noted from this conversation. It holds no loaded record and no jot." % session.id]
        if len(fresh) != len(mine):
            said.append("Left out: %d thing%s said that %s read back before or %s being read now. What is printed is the rest."
                        % (len(mine) - len(fresh), "" if len(mine) - len(fresh) == 1 else "s", "was" if len(mine) - len(fresh) == 1 else "were",
                           "is" if len(mine) - len(fresh) == 1 else "are"))
        return session, said

    def _kept(self, session, options):
        """What to say where the command line asks for something the open session was not opened with."""
        asked = CORRECTIONS if options.get(CORRECTIONS) else ""
        if asked == (session.origin.get("only") or ""):
            return []
        return ["It keeps what it was opened with: %s. `--%s` is given when a reading is opened and not after." % (
            "corrections only" if session.origin.get("only") else "every time the owner steered the work", CORRECTIONS)]


MEMBER = EarlierOpening
