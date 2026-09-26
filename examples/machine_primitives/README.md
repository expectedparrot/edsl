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
| [Continuous double auction](double_auction.py) | Price/time ordering, atomic account and order updates | One-unit orders; admission failures are `require` no-ops |
| [Binary LMSR](binary_market.py) | Stable numerical expressions, portfolio transformations | Unconstrained purchases; negative cash permitted |
| [Batch auction](batch_auction.py) | Stop-on-first-failure fold, deterministic ties, uniform clearing price | Clearing only; one unit per trader; no cash settlement or income schedule |

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
