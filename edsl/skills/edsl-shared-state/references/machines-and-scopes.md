# Machines and scopes

## Machine contract

A `Machine` is a versioned, data-only transition system. It contains:

- `constants`: immutable configuration referenced with `constant(name)`;
- `fields`: typed persistent values and initial expressions;
- `commands`: typed inputs, optional requirements, and atomic effects;
- `view`: derived values exposed to readers without adding stored fields;
- optional `complete_when`, `close_effects`, and versioned algorithm dependencies.

Build expressions with the EDSL shared-state DSL (`field`, `arg`, `local`,
`choose`, comparisons, collection operations) and effects such as `assign`,
`put`, `append`, `require`, `reject`, and `when`. Keep transitions declarative
and JSON-serializable. Python authoring helpers may construct these objects, but
runtime behavior must be represented in the serialized definition.

Validate with `machine.validate()`. `Machine.to_json()` emits the versioned
definition and `Machine.from_json()` reads it. `Runtime.initial_state`,
`Runtime.execute`, `Runtime.render_view`, and `Runtime.complete` are useful for
local deterministic simulation. Each command evaluates its effects against one
pre-command snapshot and commits the transition atomically; a rejected command
leaves the state unchanged.

`put(..., once=True)` gives first-write-wins behavior for a key. Use it only when
retries or later writes must not replace the first accepted value. Requirements
and type declarations should encode the mechanism's actual invariants rather
than relying on survey wording.

## State spaces and scope identity

Put one or more named machines into a `SharedState`, then use a
`SharedStateMap` to assign independent spaces to stable scope keys:

```python
from edsl.sharedstate import SharedState, SharedStateMap

state_map = SharedStateMap(SharedState(poll=activity_poll), state_id="study-poll-v1")
group = state_map.by("group-17")
```

Choose a scope that matches the sharing boundary: respondent, group, session,
or another stable unit. The `state_id` identifies the definition/backend across
resumption; scope keys partition data inside that map. A new map normally means
a new state identity. Preserve the serialized map and definition to resume the
same state, and use a new identity for an independent run.

Machines with custom algorithms require the matching runtime capability. Check
`machine.required_capabilities()` and use a runtime that registers the declared
algorithm versions. Do not assume a generic installation can execute an
extension just because it can deserialize the machine.
