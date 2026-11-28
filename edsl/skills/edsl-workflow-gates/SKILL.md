---
name: edsl-workflow-gates
description: Define and verify evidence-backed gates for agent-managed research tasks with the `ep workflow` CLI. Use when a task needs an auditable definition of done, user approval, file checks, or command verification.
tags: [edsl, cli, workflow-gates, provenance]
---

# EDSL workflow gates

Use `ep workflow` to record an ordered definition of done in `.ep-workflow/`.
Gates can require user approval, agent attestation, a file or artifact, or a
command. Freeze the gate set before work begins; attest approval gates with
evidence and verify automatic gates against the project state.

This CLI feature tracks task evidence. It is separate from respondent
orchestration in `edsl.workflows` and shared-state machines used during survey
execution. See `edsl:edsl-orchestration` for respondent workflows and
`edsl:edsl-shared-state` for durable state shared across interviews.

For command syntax and worked examples, see [gate setup and verification](references/examples.md).
