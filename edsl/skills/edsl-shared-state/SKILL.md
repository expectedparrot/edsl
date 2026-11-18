---
name: edsl-shared-state
description: Design, validate, run, and inspect EDSL shared-state machines for durable state shared across interviews. Use when responses update common state, adaptive mechanisms, quotas, or scoped group state are required.
tags: [edsl, shared-state, state-machine]
---

# EDSL shared state

Use shared state when multiple interviews need to read or update durable, typed
state through explicit transitions. Keep the machine definition, its scope, and
its storage backend conceptually separate:

- `Machine` defines fields, commands, requirements, views, and completion rules.
- `SharedState` groups named machines into one state space.
- `SharedStateMap` selects a separate state space for each scope key.
- A runner or workflow backend persists state as the work executes.

Start from the invariant the mechanism needs to enforce, then express it in a
machine. Machine definitions are serializable data; do not put Python callbacks
or model calls inside a machine. Validate definitions and capability requirements
before executing them. See [machine design and scopes](references/machines-and-scopes.md).

For survey integration, attach state reads, questions, and writes in execution
order. Use typed answer references such as `question.answer`, not strings that
look like Python expressions. Pick a stable scope key for the participants who
share state, and reuse the same serialized state map when resuming a run. See
[survey execution and state provenance](references/survey-execution.md).

The `ep` CLI can validate, inspect, and locally simulate serialized Machine JSON,
then inspect shared-state bindings in saved Results. It does not author a full
Machine interactively or persist the `state simulate` dry run. See
[shared-state CLI commands](references/cli.md).

This feature is experimental and versioned. Prefer the installed EDSL package's
schemas, CLI help, and matching references over examples from another release.
For multi-step assignment, branching, Humanize delivery, or respondent-level
workflow recovery, use `edsl-orchestration`; a workflow may use shared state as
one of its coordination mechanisms.
