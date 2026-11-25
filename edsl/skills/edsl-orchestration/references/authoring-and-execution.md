# Workflow authoring and execution

## Build the protocol

Use `Workflow(name)` as an authoring builder and compile it to a serializable
`HumanWorkflow`. Each step contains a Survey, an assignee selector, dependency
edges, completion policy, optional conditions, visibility, and optional shared
state reads/writes. `after=` means a predecessor must complete successfully;
`after_settled=` waits for a predecessor to settle while allowing optional work
to be skipped.

Use typed handles from prior steps for answer/output references. Avoid manually
constructing Jinja expressions when a typed reference expresses the dependency.
Use `role("name")` to select participants by a trait. Validate that every step
has eligible participants and that each participant resolves to exactly one
executor in the `ExecutionPlan`.

## Portable experiments

`WorkflowExperiment` bundles:

- a compiled `HumanWorkflow`;
- serialized `SharedStateMap` objects referenced by the workflow;
- Agents with stable participant names and JSON-serializable traits;
- an `ExecutionPlan` routing participants to `human`, `llm`, or `scripted`;
- optional metadata, including a deterministic seed.

Portable experiments reject functional Python questions and dynamic Agent
callbacks. Algorithm implementations must be registered in the runtime that
loads the bundle. Save the JSON with `experiment.save(path)` and validate it
with the CLI before running.

## Durable run invariants

The run directory pins the experiment, stores workflow lifecycle events in
`workflow.sqlite`, and stores each shared-state map in a separate SQLite file.
The instance definition is fingerprinted. Resume with the exact same experiment
and instance ID; changing the pinned definition is an error. Keep the run
directory as a unit when backing it up or moving it.

`WorkflowExperiment.run` advances scripted work and LLM batches until completion
or a declared pause. LLM executors may call model providers. Supplying
`responses` replays answers for non-scripted work and prevents model calls;
scripted executors continue to use their configured literal answers.

Human delivery is separate from this automated run loop. Use the CLI's
Humanize lifecycle for all-human plans. The current CLI Humanize start path
requires every participant to resolve to the `human` executor and to have an
email trait. Mixed Humanize/LLM routing and arbitrary delivery adapters are not
yet exposed through the CLI.
