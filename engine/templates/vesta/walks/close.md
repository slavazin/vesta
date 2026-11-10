# Close walk

Walked by `/vesta-insight` at the end of a task, together with the steps the engine supplies. An answer
that survives its counterfactual becomes an observation. "Nothing" is an acceptable answer. Something worth
recording that no lens asked for is recorded as `off-map`. The `level` column is the lowest engagement
level at which a row or lens is used.

## Rows

| id | fires-when | fires-on | consult | owed act | level | origin |
|---|---|---|---|---|---|---|

## Lenses

| lens | angle | counterfactual | level | origin |
|---|---|---|---|---|
| friction | Which step of this session took more effort than the task warranted — named as a step, with where it happened — and would the next session pay the same cost? | Was it a one-off, or a difficulty the task itself carried, blamed on the step that met it? | quiet | seed |
| first-wrong | Where was the first attempt wrong, and what did it take to find out? | Was it a slip anyone makes, or a piece of standing knowledge that was missing? | standard | seed |
| missing-record | What decision or instruction, had it been written down, would have shaped this work from the start? | Where would that record misfire or reach too far on the next task? | standard | seed |
| unnoticed | What went unnoticed for a while that a record, a checklist or an automatic check could have shown sooner? | What about it could no record or check have foreseen? | standard | seed |
| chose-alone | Which choice between real alternatives did the agent make on its own in this session, where the owner might have chosen otherwise and the same choice will come up again? | Would the owner care which way it went, or would any of the options have served? | active | seed |

## Choices

The test for turning something the owner decided in a session into a proposed decision. Apply it in order;
the first part that fails ends it, and the choice stays a note.

1. **There was a real alternative.** At least one other option was on the table and was turned down. A
   plain instruction ("use the blue one") with nothing rejected is a preference.
2. **It will come up again.** The situation can be described without this task: finish the sentence "the
   next time someone is …". If the sentence cannot be finished, it was a one-off.
3. **The project does not already settle it.** If a file, a setting or the code now enforces the choice,
   the project is the record; write nothing.
4. **No decision already covers it.** Read the `when` lines listed with this step. Where one covers the
   same situation, the choice changes or confirms that decision — propose an edit to it, or nothing — and
   does not become a second record.

A choice that passes all four is proposed as a decision, with the owner's words as its evidence.
