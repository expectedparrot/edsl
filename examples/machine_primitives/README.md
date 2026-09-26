# Machine primitive example corpus

Start here when asking a coding agent to build a new mechanism. These examples
are **language design probes**, not a production economics library. Each
`build_machine()` returns an ordinary `Machine`; its behavior survives JSON
transport and runs under `Runtime()` with an **empty algorithm registry**.
Python helpers construct expressions. They are never callbacks during execution.

| Start with | Pattern to reuse | Deliberate boundary |
| --- | --- | --- |
| [Running ledger](running_ledger.py) | Ordered fold with a structured accumulator | No account authorization |
| [Serial dictatorship](serial_dictatorship.py) | Latest submissions, priority ordering, evolving capacity | One selected item per claimant |
| [Deferred acceptance](deferred_acceptance.py) | Lexical bindings, bounded queue processing, tentative matching | Strict, possibly incomplete rankings; unmatched applicants permitted |
| [Continuous double auction](double_auction.py) | Price/time ordering, atomic account and order updates | One-unit orders; assertions report explicit admission rejections |
| [Binary LMSR](binary_market.py) | Stable numerical expressions, portfolio transformations | Unconstrained purchases; negative cash permitted |
| [Batch auction](batch_auction.py) | Stop-on-first-failure fold, deterministic ties, uniform clearing price | Clearing only; one unit per trader; no cash settlement or income schedule |
| [Seeded allocation](seeded_allocation.py) | Stable-ID lottery and independent keyed bonus | Study-assigned IDs; predictable seed |
| [Monetary settlement](monetary_settlement.py) | Exact decimal text, integer balances, fee rounding | Fixed accounts; no authorization or currency conversion |
| [Survey quotas](survey_quota.py) | Atomic per-type admission and personal eligibility | Counts admissions; no abandonment reclamation or authentication |
| [Reason discovery](reason_discovery.py) | Growing catalog and streak-based stopping across distinct agents | Text normalization only; saturation can miss rare reasons |
| [Question coverage](question_coverage.py) | Fixed personal assignments and idempotent answer counting | Sequential interviews; assignments do not reserve capacity |
| [Pairwise comparisons](pairwise_comparisons.py) | Online logistic scores, adaptive pair selection, exploration, and fixed randomized options | No uncertainty estimates or concurrent assignment reservations |
| [Appointment booking](appointment_booking.py) | Hold/confirm/release lifecycle with fenced reservation IDs | Explicit release; no automatic abandonment expiry |
| [Price elicitation](price_elicitation.py) | Integer binary search with replayable observations | Assumed in-range monotone threshold; bounded Survey slots |
| [Balanced assignment](balanced_assignment.py) | Greedy marginal balance and seeded ties | Order-dependent; no concealment or exact-balance guarantee |
| [Team formation](team_formation.py) | Atomic role seats and persistent personal membership | No departures, waitlists, or role verification |

Run from the repository root with an installed EDSL development environment:

```sh
python -m examples.machine_primitives
python -m examples.machine_primitives --output /tmp/machine-primitives
```

This makes no model or remote calls. Each example is serialized and restored
before running its `DEMO`. Exports include a `.machine.json` definition and a
`.replay.json` record with commands, expected state/view, operation inventory,
and serialized size. These are Machine JSON definitions, not Jobs or `.ep`
packages, so do not pass them directly to `ep run`.

For a coding-agent task, name the closest example, specify the desired behavior
and invariants, and request a builder, deterministic replay, round-trip test, and
failure cases. Run with the empty `Runtime()` to catch accidental dependence on
`algorithm(...)` or a registered backend. Keep any newly discovered limitation
in the canonical [Mintlify chapter](../../docs/en/latest/shared-state/algorithms-and-reference.mdx).

Verification lives in
[`test_primitive_examples.py`](../../tests/sharedstate/test_primitive_examples.py)
[`test_machine_iteration.py`](../../tests/sharedstate/test_machine_iteration.py),
and [`test_machine_records.py`](../../tests/sharedstate/test_machine_records.py).
It compares supported paths against existing algorithm implementations and also
checks independent properties: capacity constraints, absence of blocking pairs,
conservation, lexical scope, iteration exhaustion, and rollback in SQLite.
Comparisons establish the tested domain, not equivalence for every malformed
input or every feature of the full asset-market implementation.

The canonical manual documents primitive semantics and the current design gaps.
Existing algorithm-backed examples remain available for compatibility and as
comparison implementations; this corpus does not silently replace them.

The running ledger and deferred acceptance examples also demonstrate `T.record`
for nested state. Omitted required members and unexpected members are distinct
from nullable values. The remaining language-design checklist is tracked in
[issue #2665](https://github.com/expectedparrot/edsl/issues/2665).

The ledger declares a `fold(..., accumulator_type=...)` invariant. The runtime
checks the seed and every carried value. Deferred acceptance declares an
`iterate(..., state_type=...)` invariant with the same contract. Omit these options when changing accumulator shape is deliberate.
All examples run under the default shared evaluation and data-size quotas; see
[execution limits](https://docs.expectedparrot.com/en/latest/shared-state/machines#execution-limits)
for configuration and the trusted-callback boundary.

Each replay export includes a derived `capabilities` manifest. Inspect it with
`machine.required_capabilities()` and compare a destination advertisement with
`machine.check_capabilities(runtime.capability_manifest())`. The runtime checks
again before execution. The separate `.machine.json` artifact and its fingerprint
are unchanged by deriving this metadata. See the canonical manual's
[interpreter capabilities](https://docs.expectedparrot.com/en/latest/shared-state/machines#interpreter-capabilities)
for exact-version matching and the local/remote deployment boundary.

The continuous auction now uses `assert_(condition, code="...")` for admission.
Its demo includes a refused order and a hold no-op; exported replays include a
`decisions` list with status and reason code for every command. Successful paths
still match the registered algorithm; invalid admission preserves state while
returning a rejection instead of the registered implementation's exception.
See [explicit rejection](https://docs.expectedparrot.com/en/latest/shared-state/machines#explicit-rejection-and-outcomes)
for disclosure, idempotency, failure, and close semantics.


The lottery and settlement examples use `seeded_integer`, `seeded_order`,
`decimal_units`, and `round_ratio`. Their canonical
[randomization and money chapter](https://docs.expectedparrot.com/en/latest/shared-state/randomization-and-money)
defines the versioned byte protocol and signed rounding rules. Tests in
[`test_machine_portable.py`](../../tests/sharedstate/test_machine_portable.py)
cover protocol vectors, arrival-order independence, exact conservation,
SQLite reopen/retry, and fresh-process replay. Existing market callbacks retain
their original random streams and rounding behavior.


The [survey-quota adapter](../survey_quota.py) asks respondents their type and
uses computed gates plus real survey stop rules. Run `python -m examples.survey_quota`
for a local 27-respondent demo: ten A and ten B admitted, seven screened out.
The canonical [survey-quota walkthrough](https://docs.expectedparrot.com/en/latest/shared-state/survey-quotas)
documents admission timing, concurrency, restart, identity, and deployment limits.

Run `python -m examples.machine_primitives.profile_corpus` to measure all examples'
serialized size, expression repetition, and per-transition host budget work.
This development instrumentation uses internal accounting; its measurements are
not a stable tracing API or cross-host cost schedule.


The [adaptive reason-discovery adapter](../reason_discovery.py) starts with two
reasons plus Other, asks for text only on Other, and presents additions to later
agents. `python -m examples.reason_discovery` runs a seeded five-reason population
sequentially until ten valid observations add nothing new. The canonical
[walkthrough](https://docs.expectedparrot.com/en/latest/shared-state/reason-discovery)
documents stopping, normalization, ordering, replay, and semantic-deduplication limits.

The [adaptive question-coverage adapter](../question_coverage.py) generates skip
rules to ask each agent up to three under-covered questions. Run
`python -m examples.question_coverage` for a local simulation: 67 agents provide
200 answers, reaching ten answers on each of 20 questions. The canonical
[walkthrough](https://docs.expectedparrot.com/en/latest/shared-state/question-coverage)
explains fixed assignments, partial resumption, generated routing, and the
remaining routing and concurrent-reservation limitations. The Runner now reuses
validated survey templates while giving callers isolated copies. Compare the
local five-agent execution with and without reuse using
`python -m examples.machine_primitives.profile_survey_runner` and its `--uncached`
option. This diagnostic makes no model calls and reports decode/validation
counts alongside elapsed time and the verified coverage result.

The [adaptive pairwise-comparison adapter](../pairwise_comparisons.py) assigns one
fixed pair per respondent, updates scores after valid choices, and balances
close-score comparisons with exploration. `python -m examples.pairwise_comparisons`
collects 40 comparisons from a scripted five-product population. Its
[canonical chapter](https://docs.expectedparrot.com/en/latest/shared-state/pairwise-comparisons)
documents the exact policy, scoring, resumption, actual rendered-choice tests,
and the remaining statistical and candidate-scaling boundaries; Results now preserves presented options and their read-version provenance.


Four more single-pass Survey adapters run without model calls:

```sh
python -m examples.appointment_booking
python -m examples.price_elicitation
python -m examples.balanced_assignment
python -m examples.team_formation
```

Their canonical Mintlify chapters are
[booking](../../docs/en/latest/shared-state/appointment-booking.mdx),
[price elicitation](../../docs/en/latest/shared-state/price-elicitation.mdx),
[balanced assignment](../../docs/en/latest/shared-state/balanced-assignment.mdx), and
[team formation](../../docs/en/latest/shared-state/team-formation.mdx).
The shared [application tests](../../tests/sharedstate/test_survey_applications.py)
cover independent policy references, concurrent writes, restart/replay, fresh-process
transport, actual displayed choices, and resumption. Booking probes reversible
reservations; price elicitation uses personal scopes; assignment tests competing
balance margins; team formation distinguishes stopping new enrollment from stopping
the last admitted interview. All sixteen corpus definitions execute with general
primitives and an empty algorithm registry.
