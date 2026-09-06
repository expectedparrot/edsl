# Workflow and shared-state execution contracts

The workflow graph and shared-state machine DSL remain separate: workflows
coordinate respondent tasks; machines implement deterministic state transitions.
They share JSON validation, symbolic Boolean safeguards, arity checks, and
definition fingerprints. This hardening does not merge their expression languages.

## Accept once, recover forward

A workflow response follows this sequence:

```text
ready / in_progress → committing → completed → release downstream tasks
                       │
                       └─ persisted answer + ordered state-effect intents
```

Before applying any state writes, `submit()` validates the work-item status,
instance status, idempotency key, and execution lease, then durably accepts the
answer and resolved effects in one workflow-store transaction. An expired or
replaced worker cannot accept a new response. An attempt accepted while its lease
was valid can finish its effects after lease expiry: the accepted response, not
the worker, now owns that work.

An idempotency key identifies one operation, not a particular generated answer.
Reusing it with different content is an error. Identical retries return the
existing outcome. A state operation also checks its runtime context on retry.

Each state effect is atomic in its state database. Its intent remains pending
until acknowledged in the workflow store. If a process dies between these two
commits, recovery retries the **same operation**; the state backend deduplicates
it. The workflow answer becomes completed only after every effect is acknowledged.
These guarantees require a state backend that implements the idempotency contract.

```python
# Restore the saved definition and bind the same state databases.
coordinator = WorkflowCoordinator.restore(
    instance_id, store, state_backends=state_backends
)
coordinator.recover(instance_id)
# Or recover and then continue simulated execution:
simulation.run(instance_id, resume=True, retry_policy=policy)
```

An accepted response is never regenerated to recover pending effects. A permanent
effect failure leaves an inspectable `committing` item requiring operator repair.
`store.submission_intent(item_id)` and `store.pending_effects(item_id)` expose it.
There is no automatic rollback, compensation, or transaction spanning separate
databases: external readers can observe the first effect before later ones commit.

## Observations and visibility

The first successful `open()` saves a rendered survey and shared-state versions.
Subsequent opens, including retries after a restart, reuse that saved observation.
Survey rules, memory, instructions, and groups survive rendering. Reopening a task
does not refresh its information; a new information treatment needs a new task.
Concurrent first opens converge on the saved render; extra state read audit events
can exist for a render that lost that race.

Prior workflow outputs and derived values enter the rendering context only after
their source steps settle. The runtime context excludes unauthorized raw outputs
and derived fields. This applies to whole-container access, aliases, and dynamic
lookups, not just typed references. Compilation parses dot, bracket, and `.get()`
references to report statically identifiable visibility violations early.

An explicit `derived.field("payoffs").for_participant()` projection of a
participant-keyed calculation releases only that participant's entry. It does
not authorize the rest of the table or any other private statistic. Publishing
an aggregate of private answers must be intentional—for example, a separately
authorized release step, or an explicitly projected per-participant feedback
calculation. Participant submission views still inherit their source visibility.

This is a respondent-observation boundary, not a sandbox for untrusted Jinja or
Python and not access control for database files or administrator APIs. Branches,
timing, and intentionally released derived values can also reveal information.
First-open snapshots are per task, not a simultaneous phase barrier across tasks.

## Definitions, models, and randomization

Compilation and coordinator/backend construction detach definitions from mutable
authoring objects. Workflow instances and state IDs bind to fingerprints of their
serialized definitions. Later mutation or reopening under a different definition
fails explicitly. Package build labels on EDSL objects are excluded from the
fingerprint; behavioral content and serialization versions are included.

Executor routing resolutions are pinned per task. When using `EDSLAgentAnswerer`,
the concrete model's serialized configuration is also pinned before the first
call and available through `store.model(item_id)`. A changed model on retry is
rejected. This does not pin provider-side model weights, arbitrary custom Python
answerers, or all operational run options, nor guarantee deterministic LLM answers.

```python
instance_id = coordinator.launch(participants, random_seed="study-42-replicate-1")
```

The stored seed drives keyed chance and seeded draws. Reusing it across new
instances reproduces those draws independently of operational instance IDs.
Omitting it preserves the default of using the instance ID. It is not an LLM
sampling seed. Keep randomization keys stable and distinct for independent draws.

## Language and persistence checks

Python `if`, `and`, `or`, and `not` cannot silently consume symbolic expressions.
Use shared-state `&`, `|`, `~`, and `choose()`, or workflow `all_of()`, `any_of()`,
`not_()`, and `choose()`. Unknown operations, effects, reducers, types, unsupported
versions, and malformed argument counts are rejected. These are structural
checks, not a complete static type system or a resource-bounded interpreter.

Persisted inputs, states, and public views require finite JSON data and string
map keys. `NaN`, infinities, and integer-keyed persisted maps are rejected, including
under `T.any()`. Algorithms may use numeric keys internally, but must explicitly
encode them as text in a JSON view. The Delphi and signal-schedule examples show
this conversion without changing numeric ordering inside their calculations.

## Quorum is success, not branch skipping

When a quorum succeeds, outstanding unaccepted assignments become `superseded`,
not `skipped`. Ordinary `after=source` dependencies and `source.completed` honor
the source's completion policy. Genuine branch skips retain skip propagation;
`after_settled` permits a join after either outcome.

Quorum is a minimum, not a strict response cap. Already accepted `committing`
responses finish before the step settles, so concurrent acceptance can exceed
the threshold. Late unaccepted responses to superseded assignments are rejected.
Previously delivered external invitations are not automatically recalled.
Humanize polling marks their local task records cancelled and ignores late
responses after supersession; provider-side invitations may still remain visible.

## Compatibility and rollout

Workflow serialization is now version 2. Version-1 definition files can be
imported for a **new** run, but an existing version-1 instance cannot silently
resume under version-2 lifecycle/visibility semantics. Back up old databases and
use new instances, or design and audit an explicit migration. No automatic
workflow-data migration is provided by this change.

Machine definitions carry language version 1; unsupported versions fail. State
stores pin the definition and runtime version. A legacy state store without a
definition record is rejected unless its owner verifies the original definition
and opts into `SQLiteStateBackend(..., adopt_legacy_definition=True)`. That adoption
is recorded but cannot prove what definition originally produced the old data.

External delivery remains at-least-once unless the provider honors the supplied
idempotency key. A crash after Humanize creates a survey but before local recording
can duplicate an invitation. This hardening does not claim exactly-once delivery.

Regression coverage lives in `tests/workflows/test_workflow_contracts.py` and
`tests/sharedstate/test_state_contracts.py`, alongside the workflow gallery,
machine execution, serialization round-trip, and runner integration suites.
