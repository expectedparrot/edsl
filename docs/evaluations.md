# Batched judgment evaluations

`Evaluation` is a fluent workload for models that return typed judgments over
supplied context. It uses a dedicated batch executor, independent of the EDSL
interview runner, and returns ordinary `Results`.

```python
from edsl import (
    JudgmentModel, ProbabilisticResponse, QuestionMultipleChoice,
    ScenarioList, Survey,
)

survey = Survey([
    QuestionMultipleChoice(
        question_name="sentiment",
        question_text="What sentiment does {{ text }} express?",
        question_options=["positive", "neutral", "negative"],
        probabilistic_response=ProbabilisticResponse(resolution="mode"),
    ),
    QuestionMultipleChoice(
        question_name="topic",
        question_text="What is the main topic of {{ text }}?",
        question_options=["product", "delivery", "other"],
    ),
])
scenarios = ScenarioList.from_list("text", [
    "The product is excellent.",
    "My delivery arrived late.",
])
models = [JudgmentModel("jev-1.13.0", service_name="typesafe")]

evaluation = survey.to_evaluation().by(scenarios).by(models)
plan = evaluation.compile()             # Validates; no inference calls
print(plan)                            # 2 results, 2 batched requests
results = plan.run()                    # Requires TYPESAFE_API_KEY
results.select("answer.*", "distribution.*")
```

Set `TYPESAFE_API_KEY` in the process environment or your local gitignored `.env`
file. Credentials are read at execution time and are not serialized. Calls go
directly to TypeSafe; this initial backend does not offload to Expected Parrot.
See the provider's [API reference](https://docs.typesafe.ai/api) and
[model limits](https://docs.typesafe.ai/models).

## Fluent construction

`.by()` accepts an individual object, multiple objects of the same kind, or a
collection. Bind models and scenarios in either order; optionally bind agents.
Agents × scenarios × models × iterations produce result rows. Missing scenarios
use an empty scenario. Missing agents use a neutral evaluation instruction.
Models must be supplied explicitly as `JudgmentModel` objects.

Like `Jobs`, successive scenario/agent bindings form Cartesian combinations by
merging their traits. A later model binding replaces the previous model set.
Multiple models evaluate the same workload separately, not as fallback routing.

Every scenario field is sent in the structured state, together with agent traits
and their codebook. Question templates support both `{{ field }}` and
`{{ scenario.field }}`, as well as `{{ agent.trait }}`. Agent instructions and
applicable survey instructions are included in each judgment. Missing variables
fail compilation.

## Supported questions

| EDSL question | Judgment | Answer behavior |
| --- | --- | --- |
| `QuestionMultipleChoice` | Choice | Select an original option; preserve its distribution |
| `QuestionYesNo` | Binary probability (TypeSafe Noul) | Explicit Yes/No options in either order |
| `QuestionLinearScale` | Score | Requires a descriptive label for **every** level; resolve to an original scale option |

Without an explicit `ProbabilisticResponse`, the answer is the modal option.
With a contract, `resolution="none"` retains the distribution and leaves the
answer `None`; `resolution="sample", seed=42` samples reproducibly in EDSL.
Distribution order always matches the rendered EDSL question options. Provider
option IDs are internal and never become user-facing answers.

A Score's fractional expected **level index** is retained in the raw typed
response. It is not substituted for an EDSL discrete scale answer. TypeSafe
confidence is retained there too; it is a distribution statistic, not an
independently established probability of correctness.

Live Jev responses can report a score differing from the mean of the returned
probabilities (observed differences of 0.01 are consistent with separate
rounding). EDSL validates each field independently, resolves answers from the
distribution, and retains `score_from_distribution` and `score_difference` in
the raw response metadata for auditing.

The TypeSafe adapter also handles observed probability vectors summing to 0.99
or 1.01. If all entries are valid probabilities and the total differs from one
by at most 0.01, it divides by that total before EDSL validation. The unmodified
vector is retained as `reported_probabilities`, with an explicit
`probability_normalization` audit record. Larger discrepancies remain errors;
other providers' vectors are not automatically normalized.

Compilation rejects free text, other unsupported question types, skip/stop rules,
answer piping, survey memory, option randomization/pinning, custom question
presentation/answering templates, and dynamic/direct-answer agents. It reports
all detected incompatibilities before making any inference calls. Use a normal
EDSL job for these features, or a separate processing stage after evaluation.

## Batching, concurrency, and recovery

All compatible questions sharing a context are packed into one request where
possible. Different contexts and models use separate requests. The compiler uses
conservative UTF-8 JSON byte budgets below TypeSafe's documented token limits;
these are not exact tokenizer counts. Oversized individual contexts fail
compilation rather than being truncated. You can set a smaller question limit:

```python
from edsl import Cache

cache = Cache()
results = evaluation.run(
    max_questions_per_request=20,
    max_concurrency=8,
    cache=cache,
)
# Inside an existing event loop:
results = await evaluation.run_async(cache=cache)
```

Only a bounded number of async workers run, and TypeSafe transient failures are
retried with backoff. Successful validated **batches** are cached using their
complete context, typed question definitions, service, model, and iteration.
Changing batch composition changes cache identity. `n=N` creates N iterations;
it does not currently reuse one inference across iterations.

Pin a versioned model for reproducible research. When using `jev-latest`, cached
responses remain associated with that requested alias until you use a fresh
cache. The actual answering model version is preserved in each raw answer.

On failure, `EvaluationRunError.partial_results` contains completed rows and the
cache holding successful batches. Re-run with that cache to retry incomplete
work. Cancellation also retains already-written batches in a caller-supplied
cache. Partially valid provider responses are rejected as a batch.

For cache reuse across processes, save it separately with
`cache.save("evaluation-cache.json.gz")` and reload with
`Cache.load("evaluation-cache.json.gz")`. Current `Results.ep` packages preserve
answers and batch provenance but do not retain the execution cache or per-run
`cache_used` flags.

Raw answers carry a batch key and batch question names. Shared token usage and
the complete batch response are attached to the first question in the batch
only, avoiding duplicated token totals. `cache_used` distinguishes replayed
usage from new inference. Monetary cost estimation is not implemented here.

## Persistence

```python
from edsl import Evaluation, Results

evaluation.save("evaluation.ep")
restored = Evaluation.load("evaluation.ep")
results.save("results.ep")
results = Results.load("results.ep")
```

Evaluation definitions also support `to_dict()` / `from_dict()` and JSON
save/load. Compiled plans are in-memory snapshots with an inspectable
`to_dict()`; save the Evaluation definition for durable reuse. Results retain
judgment model identity through serialization even when version metadata is
omitted. This initial public interface is Python; no new CLI evaluation command
or remote execution service is introduced.

## Additional providers

Subclass `JudgmentModel`, declare `JudgmentCapabilities`, and implement
`async_evaluate(state, questions, *, client)`. Register the provider using
`JudgmentModel.register(service_name, provider_class)` before construction or
deserialization. The executor supplies a shared async HTTP client and expects
typed answers, actual model identity, and input/output token usage. Binary
requests use `type="binary"` and answers use `probability`; TypeSafe's adapter
translates Noul at the transport boundary. Batch support is a separate capability
from the supported judgment primitives.
