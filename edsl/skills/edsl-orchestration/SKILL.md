---
name: edsl-orchestration
description: Design, validate, run, and recover durable EDSL respondent workflows spanning human and AI participants. Use for multi-step assignment, branching, fan-in, repeated work, and Humanize delivery.
tags: [edsl, orchestration, respondent-workflows]
---

# EDSL respondent orchestration

Use `edsl.workflows` when a study is a durable graph of respondent work: who
gets each step, when it becomes ready, which earlier answers it can observe,
and how completion or retries release later work. This is the respondent
orchestration API; `ep workflow` is a separate CLI for research-task evidence
gates.

Start with `Workflow` to author steps and dependencies. Use conditions, quorum
completion, derived values, and bounded repeats only when the protocol requires
them. Route participants with an `ExecutionPlan` to `human`, `llm`, or
`scripted` executors. Use shared state when transitions need durable common
state across interviews; see `edsl-shared-state` for its Machine and scope
contracts.

For portable bundles, use `WorkflowExperiment` to combine the compiled workflow,
state maps, participants, and executor plan. Validate and inspect the serialized
bundle before execution. Choose `ep orchestration run` for scripted/LLM runs or
answer replay. Choose `start`/`sync`/`status` for Humanize delivery. Read
[CLI lifecycle details](references/cli-lifecycle.md) before starting a run,
especially when model calls or participant invitations are involved.

The API and serialized format are experimental and versioned. Preserve the
experiment definition, output directory, and instance ID when resuming. Use the
same replay answer file on every replay-driven resume. Read
[workflow authoring and execution](references/authoring-and-execution.md) for
the object model and durable-run invariants.

Fetch complete, version-matched workflow examples through the CLI with
`ep skills show edsl-orchestration --example <path>`. Use
`ep skills list --routing` to find available examples, or see the
[example guide](references/examples.md). The Humanize delivery example requires
two explicit email addresses before it can create a run or send invitations.
