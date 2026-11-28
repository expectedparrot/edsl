---
name: edsl-judgment-evaluations
description: Design and run EDSL Evaluation workloads for batched, typed model judgments over supplied contexts, then inspect their Results.
tags: [edsl, evaluation, typed-judgments]
---

# EDSL judgment evaluations

Use this skill when a task needs a model to classify, choose among explicit
options, assign a binary probability, or score a labeled scale for many
contexts. `Evaluation` batches compatible questions that share a context and
returns the results in EDSL's standard `Results` container. Use regular EDSL
`Jobs` when the task needs generated text, interview execution, branching, or
other normal survey-runner behavior.

## Define and validate the workload

Create a `Survey` with supported typed questions, bind scenarios and an
explicit `JudgmentModel`, then compile before running. Compilation validates
the workload and snapshots it without making inference calls.

```python
from edsl import (
    JudgmentModel,
    QuestionMultipleChoice,
    ScenarioList,
    Survey,
)

survey = Survey([
    QuestionMultipleChoice(
        question_name="sentiment",
        question_text="What sentiment does {{ text }} express?",
        question_options=["positive", "neutral", "negative"],
    ),
])
scenarios = ScenarioList.from_list(
    "text", ["The product is excellent.", "My delivery arrived late."]
)
evaluation = (
    survey.to_evaluation()
    .by(scenarios)
    .by(JudgmentModel("jev-1.13.0", service_name="typesafe"))
)
plan = evaluation.compile()  # No model calls
results = plan.run()         # Requires TYPESAFE_API_KEY
```

Reopen the delivered package with `ep validate --file review.ep --type evaluation`. This compiles the saved workload offline and reports its request count, judgment count, and scenario field names. For a blind review, pass allowed fields explicitly, e.g. `--allow-scenario-field case_id --allow-scenario-field message`. Keep human labels in a separate local key. This check verifies scenario column names; inspect allowed text and any agent traits separately for unintended disclosures.

Use `await evaluation.run_async()` inside an existing event loop. Bind agents
only when their traits or instructions are part of the judgment context.

Before execution, confirm that the intended behavior fits the supported
semantics:

- Supported questions are multiple choice, yes/no, and linear scale. Linear
  scales need a descriptive label for every level.
- Free-text questions, answer piping, skip/stop rules, survey memory, option
  randomization/pinning, custom question templates, and dynamic or direct-answer
  agents are rejected during compilation. Do not silently approximate these
  features; use a regular EDSL job when they are required.
- Model bindings are explicit. Scenarios and agents combine with models as a
  cross-product; multiple models each evaluate the workload.
- Only visible agent traits are included in the judgment state. Scenario fields
  are sent as context, so avoid putting secrets in scenarios.

The built-in TypeSafe provider reads `TYPESAFE_API_KEY` from the process
environment at execution time. Keep credentials out of evaluation definitions
and serialized packages.

## Run, inspect, and recover

Use the normal `Results` analysis methods for answers and metadata. The default
answer is the modal option; `distribution.*` contains the probability vector in
the rendered option order. `resolution_*` fields record any configured
probabilistic resolution. Provider output, model version, and batch membership
are retained in `raw_model_response`.

```python
results = evaluation.run(max_concurrency=8, max_questions_per_request=20)
answers = results.select("answer.*", "distribution.*")
```

If a run raises `EvaluationRunError`, inspect `error.partial_results`. It
contains completed rows and the cache entries for validated batches. Re-run
with that cache to retry incomplete work. Save the cache separately when it
must be reused across processes; a Results package does not retain the
execution cache or per-run cache-used flags.

Save an evaluation definition with `evaluation.save("evaluation.ep")` and
restore it with `Evaluation.load(...)`. Results also support their regular EDSL
serialization. Evaluation definitions can be serialized, but this feature
does not submit work to Coopr: calls go directly from the executing Python
process to the configured judgment provider.
