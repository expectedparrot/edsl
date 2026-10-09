One additional stress test for the shared-state design: a chained ultimatum game with asynchronous human respondents.

Example:

- Respondent 1 proposes an offer to Respondent 2.
- Respondent 2 accepts/rejects Respondent 1's offer, then proposes an offer to Respondent 3.
- Respondent 3 accepts/rejects Respondent 2's offer, then proposes an offer to Respondent 4.
- This continues until the last respondent, who only responds to the previous offer.

This fits the shared-state model conceptually:

- A `SharedRegister` can hold the current outstanding offer.
- A `SharedLog` can record the full chain of offers, responses, timestamps, and respondent ids.
- The survey questions can read `shared_state.current_offer.amount`, `shared_state.current_offer.from_respondent_id`, etc.
- After a middle respondent answers, the survey appends their response to the log and replaces the current offer with their new offer.

However, this example highlights an important requirement for human surveys: support for asynchronous running.

For sequential LLM runs, this is straightforward because the engine controls order. For humans, respondents may arrive out of order, pause, refresh, abandon, or submit at nearly the same time. The shared-state API therefore needs more than after-question writes. It needs runtime semantics for gated entry, turn claiming, waiting, and stale-state handling.

Possible affordances:

1. Before-question shared-state actions

   A respondent may need to claim a turn or read a state snapshot before the question is rendered. For example:

   ```python
   claim = shared_state.turn_queue.claim_next(
       respondent_id="{{ respondent.id }}",
       as_="turn_claim",
   )
   ```

   The returned claim can then be used in question text, skip logic, and writes.

2. State conditions for question availability

   A page/question may need to wait until a required shared-state condition is true:

   ```python
   wait_until="{{ shared_state.current_offer.exists }}"
   ```

   or:

   ```python
   wait_until="{{ shared_state.current_offer.to_position == scenario.respondent_position }}"
   ```

   Humanize could display a waiting page, refresh/poll, or notify the respondent when their turn is ready.

3. Atomic claim-and-read operations

   Reading the current offer and claiming the right to respond to it should be atomic. Otherwise two respondents could see and respond to the same outstanding offer.

   This suggests primitives like:

   - `SharedQueue.claim_next(...)`
   - `SharedRegister.compare_and_set(...)`
   - `SharedCapacityPool.reserve(...)`

   These operations should return values and versions that can be stored in Results metadata.

4. Write failure control flow

   Human surveys need explicit behavior when a shared-state write fails because the state has changed since render:

   - re-render the question with fresh state
   - show a "turn already taken" / "slot no longer available" message
   - route to a fallback question
   - mark the respondent as expired or skipped

   This should be part of the shared-state write declaration rather than left as an ad hoc frontend behavior.

5. Results provenance

   For analysis, each result should preserve:

   - the shared-state snapshot/version read by the respondent
   - the claimed turn/task, if any
   - attempted writes
   - successful writes
   - failed writes and failure reasons
   - timestamps for claim, render, submit, and commit

   This is essential because two respondents in the same nominal survey may have seen different shared states.

This example makes me think the v1 design should explicitly include an async human mode, even if the first implementation is narrow. The key addition is probably not a large number of domain-specific objects. It is a small set of general concurrent primitives plus lifecycle hooks:

- before-render read/claim actions
- after-answer write actions
- atomic operations with returned values
- wait/gating behavior
- write failure policies
- metadata history in Results

Without these, shared state works well for sequential agent simulations, but the most interesting human use cases become fragile.
