# A complete Gemini audit of the shared-state examples

## Purpose

This audit asks a real model to participate in every retained shared-state
machine. It is not merely a transition test: each Survey gives Gemini a concrete
decision, private information where appropriate, and the visibility schedule
required by the mechanism. The complete run used `gemini-2.5-flash`, local EDSL
execution, fresh model calls, and a 45-second per-game limit.

The executable suite is `examples/shared_state_gemini_game_smoke.py`; its complete
machine-readable output is `examples/shared_state_gemini_complete_audit.json`.

## Coverage and reliability

- 36 of 36 retained machine families have substantive Gemini wrappers.
- 32 completed successfully in the bounded complete run.
- 4 timed out: resource allocation, budget allocation, repeated forecasting, and
  collaborative document revision.
- A timeout did not abort later games, confirming that the new per-game isolation
  works.
- Independent deterministic tests cover all 36 state machines, so these four
  timeouts implicate inference/task observability rather than known transition
  failures.

## What the successful runs showed

### Strategic games

- The dictator transferred 25 of 100.
- In the trust game the sender transferred all 100 and the receiver returned 150
  of the tripled amount, producing an equal division.
- Both players defected in the one-shot matrix game and in all three rounds of the
  repeated game. Snapshot versions were exactly `[0,0]`, `[2,2]`, and `[4,4]`.
- The ultimatum proposer offered 50 and the responder accepted.
- Nash demands were 50 and 50; money requests were 12 and 15.
- Centipede stopped correctly after a take at node one; downstream interviews were
  skipped.
- In bilateral trade the buyer offered exactly the seller's cost, 30, and the
  seller rejected. In the richer negotiation framing, a 40 offer was accepted.

These differences are valuable: seemingly similar payoff structures can produce
different behavior because the information and framing supplied by the Survey are
part of the experimental design.

### Markets and allocation

- The sealed second-price auction produced truthful bids 80, 70, and 40; the
  winner paid 70.
- The continuous double auction crossed a 69 bid with a 31 ask and traded at the
  resting ask of 31. Interview audit identifiers were preserved.
- The ascending auction produced bids 1, 2, and 3 despite private values 45, 65,
  and 55. Gemini treated the visible increment as a minimal next bid rather than
  reasoning toward willingness to pay. This wrapper needs clearer stopping and
  utility instructions before it represents an economically meaningful auction.
- The binary LMSR market tracked quantities, transaction costs, cash, positions,
  and settled wealth. The pessimistic trader profited when the event resolved
  false.
- Deferred acceptance matched A to North and B to South. Serial dictatorship
  assigned A to hike, B to bike ride, and C to sailing. Both finalized from typed
  participant-count predicates without synthetic closer agents.
- Coalition capacities were enforced and the fifth request was rejected.
- Atomic work claiming gave distinct items to two concurrent workers and both
  completions were recorded.

### Deliberation and shared artifacts

- Delphi produced two complete snapshot rounds and closed only after all six
  estimates. Read versions were `[0,0,0]` followed by `[3,3,3]`.
- Agenda construction produced two proposals followed by two informed ballots;
  each participant observed the preceding committed version.
- Private signals were revealed just before each question. With live visibility,
  every participant saw exactly their own correct signal in each round.
- The message board accumulated three serial, context-aware contributions.
- Concurrent register and counter examples worked mechanically, although identical
  unconditioned personas converged on the same activity. That is a persona-design
  result, not evidence of state contagion: every snapshot read was version zero.

## Defects found during the audit

The exercise found implementation defects that schema-only tests had missed:

1. JSON changed numeric nested-map keys between commits in the repeated game.
2. Runtime identity, role, and round capabilities were not passed to DSL
   expressions.
3. Delphi could finalize on a partially completed concurrent round.
4. LMSR portfolios were declared but never updated.
5. `before_question` commands were described by the DSL but rejected by Survey.
6. Lazy concurrent snapshot capture interacted incorrectly with before-question
   writes.
7. Fake one-option closer questions could return null and silently prevent close
   effects.
8. A single slow inference could previously block the entire multi-game audit.

Items 1–5, 7, and 8 have direct fixes. Item 6 is now rejected at job creation;
correct support requires a pre-round write barrier or per-interview overlay.

## Design limitations revealed

### Results should include exit views

`Results.shared_state` stores raw exit snapshots. Derived public views—agenda
scores, current prices, forecast summaries, privacy-filtered fields—are not
materialized there. Consequently, analyzing a completed run requires reconstructing
the machine runtime rather than simply reading Results. Each exit snapshot should
include a canonical context-free public view where one exists, while explicitly
contextual views should be available through their audited reads.

### Completion counts need configuration

Typed completion removed fake closers, but expected participant counts are now
constants in the matching specifications. A reusable machine needs those values
configured when instantiated. This argues for a small, serializable machine factory
or parameter-binding operation rather than editing module-level `SPEC` objects.

### Round barriers should be first-class

Snapshot reads are well defined, but setup writes and finalization also need barrier
semantics. The scheduling vocabulary should distinguish:

1. setup writes for every participant;
2. capture of the common round snapshot;
3. concurrent questions and answer writes; and
4. completion/finalization after the round closes.

Rejecting unsafe combinations is preferable to silent inconsistency, but it is not
the final API.

### Model failures need task-level evidence

Four very small workflows exceeded 45 seconds. The audit can now continue, but the
timeout record does not identify the interview, question, provider attempt, or last
known task state. Results or an attached error report should preserve that evidence
even when a bounded run is interrupted.

### Commands should return analyzable advisory details

Writes correctly make no durable promises to callers, but mechanism events would be
more useful if the advisory outcome included a typed reason such as `capacity_full`,
`require_false`, `matched`, or `unchanged`. The committed state remains authoritative;
the reason improves debugging and explanation.

## Recommended next implementation order

1. Add canonical exit views to `Results.shared_state`.
2. Add barrier-level setup and finalization to round schedules.
3. Add serializable machine parameter binding for counts, capacities, and rules.
4. Preserve task-level timeout and provider-attempt evidence.
5. Add typed advisory reason data to state-write events.
6. Repeat the 36-game audit with multiple seeds and compare behavioral stability.

The central conclusion is encouraging: the small DSL can express a surprisingly
wide range of economic and collaborative mechanisms, and its transactional core is
holding up. The remaining problems are concentrated at the boundaries—schedule
phases, lifecycle configuration, inference observability, and Results ergonomics—
which is exactly what realistic end-to-end examples are useful for discovering.
