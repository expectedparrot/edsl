# Shared-state execution matrix

This is the executable coverage record for the experimental shared-state DSL.
The authoritative tests are:

- `tests/sharedstate/test_all_machines_execution.py`
- `tests/sharedstate/test_game_runner_integration.py`

## What “executed” means

Every retained machine is instantiated from its serialized definition, validated,
run through a real `SQLiteStateBackend`, read back through its public view, and
JSON-serialized. The test asserts:

1. each command commits atomically and in order;
2. explicit close effects run where the mechanism requires settlement;
3. declared completion predicates hold after the supplied path;
4. the final public view contains the expected substantive outcome; and
5. the machine inventory and test inventory are exactly equal.

This is stronger than schema validation. It exercises the runtime evaluator,
transaction boundary, JSON round trips, close behavior, public views, and the
algorithms used by the examples.

## Machine coverage

| Family | Machines exercised |
| --- | --- |
| Basic shared structures | register, log, counter map, document, message board, work pool |
| Deliberation and allocation | agenda, budget pool, coalition pool, resource board, Delphi panel, forecast, signal schedule |
| Matching | match pool, deferred acceptance |
| Markets and auctions | ascending auction, sealed auction, double auction, binary market |
| Canonical economic games | ultimatum, dictator, trust, centipede, matrix, repeated matrix, Nash demand, money request, beauty contest, market entry, common pool |
| Information and contracts | cheap talk, signaling, principal-agent, bilateral trade, negotiation |
| Social choice | voting game |

There are 36 machine modules in `examples/shared_state_dsl/`, and all 36 have a
meaningful transition vector and semantic outcome oracle.

## End-to-end Runner coverage

Two representative mechanisms also run through normal EDSL Survey execution:

- **Ultimatum game:** two scoped pairs run proposer before responder under
  `grouped_round_robin`; each pair commits offer, response, and automatic close.
- **Sealed second-price auction:** three bidders run concurrently with snapshot
  visibility; every bidder sees the same pre-bid state, all bids commit, and the
  completion predicate triggers deterministic settlement.

These tests cover both major scheduling semantics: live ordered observation and a
concurrent snapshot barrier. They also confirm that state definitions, read/write
events, entry snapshots, and exit snapshots survive in `Results.shared_state`.

## Defects found by execution

The matrix found a JSON-boundary bug in the repeated matrix game: numeric mapping
keys changed type after persistence because JSON object keys are strings. Its round
and seat identifiers are now explicitly textual in the machine type and command
inputs. This is why every example needs an execution vector in addition to static
definition validation.

The ascending auction deliberately records the winning interview identifier rather
than accepting an untrusted bidder identifier as command input. Its low-level test
therefore checks price settlement; interview identity is supplied by the Runner
execution context.
