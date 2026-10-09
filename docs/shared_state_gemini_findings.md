# Gemini shared-state behavioral test findings

`examples/shared_state_gemini_game_smoke.py` runs small real-model interviews
against the experimental shared-state implementation. The suite currently covers
22 mechanisms and deliberately includes serial, simultaneous, repeated-round,
early-stop, explicit-close, and algorithm-backed state machines.

## Defects found and fixed

1. **Runtime identity context was missing.** Machine expressions using
   `current("interview_id")`, `current("name")`, `current("role")`, or
   `current("round")` received no value. Resolved operations now carry a private
   runtime capability context. Sensitive traits are not copied into state events.
2. **Repeated matrix keys were not JSON-stable.** Numeric mapping keys changed to
   strings after persistence. Round and seat identifiers are now explicitly text.
3. **Delphi could converge on a partial concurrent round.** The convergence reducer
   compared a complete first round with a one-response second round and could close
   while other writes were in flight. It now requires the configured panel size in
   both rounds.
4. **The LMSR portfolio was inert.** Trades moved outstanding quantities but did
   not update trader cash or holdings. The registered algorithm now charges the
   LMSR cost difference, records positions and transaction costs, and computes
   settled wealth.
5. **Before-question commands were not executable.** The DSL already described
   commands such as private-signal reveal and atomic work claim with
   `timing="before_question"`, but Survey rejected any write before its first
   question. Survey now serializes and executes these writes immediately before
   the anchored question and its explicit state read.

## API pressure revealed by the examples

- A machine with close effects but no `complete_when` needs an explicit closer. In
  the deferred-acceptance Survey this currently appears as a synthetic final
  participant with a one-option “close” question. A first-class end-of-round or
  end-of-schedule close step would express the intent much better.
  A live serial-matching run made the problem concrete: the closer's one-option
  answer was recorded as null, the anchored close write never ran, and assignments
  remained empty even though all preferences were present.
  The retained matching machines now declare their expected participant counts and
  typed completion predicates, so `finalize_when=game.is_complete()` closes them
  after the final real participant. No synthetic closer remains in the examples.
- Scheduling says `within_round="serial"`, while prose and other APIs naturally
  use “sequential.” Accepting one canonical term plus a checked alias would reduce
  avoidable authoring errors.
  `sequential` is now accepted and normalized to the canonical stored value
  `serial`.
- Snapshot-round completion predicates must be stable under partial-round writes.
  The Delphi fix makes its predicate safe, but the scheduler should eventually
  offer barrier-level completion/finalization so every machine author does not
  need to rediscover this rule.
- Before-question writes do not yet compose correctly with concurrent snapshot
  reads. Lazy snapshot capture can include one participant's setup write while
  excluding another participant's own write. The private-signal example therefore
  uses live visibility, whose agent-specific view preserves privacy. Correct
  snapshot composition requires either a pre-round write barrier or per-interview
  overlays on a common base snapshot.
  Jobs now reject that unsafe combination before inference with a specific error;
  live visibility remains supported.
- A slow provider request could hold the multi-game audit indefinitely. The Gemini
  harness now applies a configurable per-game timeout and records a structured
  timeout result before continuing to the next game.
- Voting currently resolves tied plurality scores by candidate declaration order.
  That is deterministic but should be an explicit configured tie-breaking rule in
  the machine definition and public result.
- Settlement and completion are separate in the binary market: `settle` records an
  outcome, but the machine has no typed completion predicate. Adding one would make
  schedule-level stopping and finalization available without special handling.

## Reproducible evidence

- `examples/shared_state_gemini_game_smoke_results_round5.json` contains voting,
  matching, market, resource-allocation, and the original problematic Delphi run.
- `examples/shared_state_gemini_game_smoke_results_round6.json` contains the fixed
  LMSR and Delphi reruns.
- `examples/shared_state_gemini_game_smoke_results_round8.json` demonstrates the
  incorrect lazy-snapshot/private-signal interaction that motivated the explicit
  live-visibility restriction.
- `tests/sharedstate/` contains deterministic regression coverage independent of
  model credentials.
