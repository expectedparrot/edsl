# Output budgets and response diagnostics

This change addresses [issue #2628](https://github.com/expectedparrot/edsl/issues/2628).

## Output limits

LanguageModel resolves omitted output limits centrally: 16,000 tokens for
recognized reasoning families or explicitly enabled thinking, and 2,000 tokens
otherwise. The policy applies across adapters, including OpenAI-compatible
providers and Google's `maxOutputTokens` parameter. Explicit limits, including
limits in serialized model parameters, remain unchanged. This changes ordinary
defaults for adapters that previously used 512, 1,000, or 2,048 tokens.

Capability recognition is an offline family-name policy, not a claim to identify
every model. Unknown IDs retain a conservative default and report `reasoning:
null`. The current policy recognizes OpenAI o1/o3/o4 and GPT-5+ families,
DeepSeek-R1/reasoner, QwQ, Magistral, names marked reasoning/thinking, and Gemini 2.5/3.
Explicit Anthropic thinking configuration and positive Google thinking budgets
also activate the reasoning default. Provider prefixes do not determine the
budget. The test service retains its existing behavior.

Mistral now forwards its configured `max_tokens`; Meta's Responses payload now
includes `max_output_tokens`. The latter mapping follows the Responses API
shape; Meta's own reference requires login, and live acceptance has not been
verified. Provider tests in this patch verify constructed requests with mocks.

`ep inspect jobs.ep` reports `output_token_policies`, including each model's
effective parameter/value and reasoning capability. A known reasoning model
below 4,000 tokens produces a warning at inspection, costing, and preflight;
EDSL does not increase an explicit limit.

Local `JobCostEstimator` detail includes `output_token_limit` and
`output_budget_cost_usd`, the cost of one call using that output allowance,
weighted by the question's reach probability. It is separate from the estimated
answer cost and is not a total-job spending cap. Raising an explicit retry
budget changes this allowance calculation without claiming the full allowance
will be used. Multi-call questions can consume multiple such allowances.

## Saved response evidence

Each runner result stores a dictionary at
`raw_model_response.<question_name>_response_metadata`. It includes, when known:

- `finish_reason`, `incomplete_reason`, `truncated`, and `visible_answer_present`.
- `input_tokens`, `reasoning_tokens`, `visible_output_tokens`,
  `completion_tokens`, and `total_tokens`.
- `attempt_count`, `retry_count`, and `provider_calls_attempted`.
- On failure, `failure.stage`, `failure.code`, `failure.message`, and
  `failure.retry_count`.
- `attempt_history` containing earlier failed-attempt evidence when a retry
  overwrites the latest answer record.

Unavailable values stay null rather than being invented. Completion totals
include reasoning; Google reports thought and candidate counts separately, so
those are combined. Original provider responses and available prompts, cache
keys, generated text, prices, and usage remain in the existing result fields.
The metadata survives JSON reconstruction, streamed runner results, and `.ep`
packages. Blocked and missing-answer tasks retain scheduling/execution evidence.

A parseable answer terminated by `length` remains usable and validated, with
`truncated: true`. If a token-limit termination has no visible text, parsing
raises `OutputTokenLimitError`, the failure code is `OUTPUT_TOKEN_LIMIT`, and the
default retry policy stops immediately. The budget is never increased
automatically. A provider's limit reason does not prove that reasoning alone
consumed the budget; the raw response and usage supply that evidence.

## Completion summaries

Use `results.completion_summary()`, `ep results summary results.ep`, or
`ep inspect results.ep`. Blocking `ep run` also includes a `completion` summary
and warns about truncated responses. Counts distinguish planned and actual rows,
provider calls, answers produced, answers validated, answered interviews,
truncated final question responses, failed interviews, and empty placeholders.
Skipped questions do not become failures. `unsuccessful_interviews` counts the
union of failures and placeholders without double-counting.

Old artifacts may have no provider-call evidence or planned-row count; those
totals remain null. `known_provider_calls_attempted` and
`questions_with_unknown_call_count` expose that limitation. Historical evidence
already discarded by a remote server cannot be recovered. Remote workers must
run the updated code to produce the new failure metadata.

## Verification

Provider calls are mocked; no paid inference is needed:

```bash
python -m pytest -q --noconftest \
  tests/language_models/test_output_token_policy.py \
  tests/runner/test_response_diagnostics.py \
  tests/test_output_diagnostics_cli.py
```

These tests exercise two non-OpenAI request adapters, Google aliases, enabled
thinking, explicit limits, preflight/inspection warnings, cost allowances,
reasoning-only exhaustion, parseable truncation, cached responses, retries,
legacy placeholders, and JSON/package reconstruction. `--noconftest` excludes
the repository-wide service-startup and cleanup hooks.

Provider format references: [DeepSeek termination reasons](https://api-docs.deepseek.com/api/create-chat-completion/),
[Gemini thinking/token usage](https://ai.google.dev/gemini-api/docs/generate-content/thinking),
and [QwQ's model card](https://huggingface.co/Qwen/QwQ-32B/blob/main/README.md).
