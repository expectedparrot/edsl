# QuestionSlop Spec

Status: draft

Owner: EDSL

Last updated: 2026-07-15

## Summary

Add a `QuestionSlop` question type that analyzes text with an external AI-text detector, initially Pangram, and returns structured JSON score metrics. It should be similar to `QuestionThinking`: the question bypasses normal agent/persona prompting and uses a specialized invigilator. Unlike `QuestionThinking`, it does not call an EDSL `LanguageModel`; it calls a detector provider adapter.

The main use case is evaluating text generated elsewhere in a survey or scenario:

```python
from edsl import QuestionSlop, ScenarioList

q = QuestionSlop(
    question_name="review_slop",
    question_text="{{ review_text }}",
    provider="pangram",
)

scenarios = ScenarioList.from_list(
    "review_text",
    [
        "This product changed my life. Highly recommend!",
        "The device worked for two weeks and then stopped charging.",
    ],
)

results = q.by(scenarios).run()
```

The answer should be a JSON-compatible dict containing normalized detector metrics plus a redacted raw provider payload when configured.

## Motivation

EDSL is often used to generate, transform, or evaluate text. A detector-backed question type gives users a reproducible way to add "AI-written / synthetic / slop" scores to a Results table without leaving the EDSL workflow.

Useful workflows:

- Score generated survey responses for AI-like writing.
- Score product reviews, comments, essays, or open-ended survey answers.
- Compare model outputs by detector score.
- Use detector score as a downstream filter, quality metric, or reward-review signal.
- Run batches with normal EDSL caching, scenarios, result selection, and persistence.

## Naming

`QuestionSlop` is concise and expressive, but it is a loaded name. The internal `question_type` can be `slop` while public docs should be careful to describe it as detector scoring rather than a definitive truth label.

Alternative names:

- `QuestionAIDetection`
- `QuestionDetector`
- `QuestionTextAuthenticity`
- `QuestionSlopScore`

Recommendation: keep `QuestionSlop` as the Python class if that is the desired product language, but make the answer schema use neutral field names like `ai_score`, `human_score`, `classification`, and `confidence`.

## EDSL API

### MVP Constructor

```python
QuestionSlop(
    question_name="slop_score",
    question_text="{{ text }}",
    provider="pangram",
    include_segments=True,
    include_raw_response=False,
    public_dashboard_link=False,
    timeout_seconds=300,
    poll_interval=0.5,
)
```

Recommended fields:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `question_name` | `str` | yes | Normal EDSL question name. |
| `question_text` | `str` | yes | Text template to render and send to the detector. |
| `provider` | `str` | no | MVP: `pangram`; future: other detectors. |
| `include_segments` | `bool` | no | Include sentence/span-level detector output when provider returns it. |
| `include_raw_response` | `bool` | no | Include redacted raw provider JSON for debugging. Default false. |
| `public_dashboard_link` | `bool` | no | Ask Pangram to include a public dashboard link. Default false. |
| `min_text_length` | `int` | no | Optional guard to avoid weak scores on very short text. |
| `on_short_text` | `str` | no | `return_null`, `score_anyway`, or `raise`. |
| `timeout_seconds` | `float` | no | Maximum time to wait for async detector completion. |
| `poll_interval` | `float` | no | Delay between task status polls. Pangram clamps very low SDK values. |

### Convenience Helper

If the common case is scoring the answer to another question, add a helper:

```python
slop_q = QuestionSlop.from_question(
    source_question=q_free_text,
    question_name="essay_slop",
)
```

This should set `question_text` to a template reference for the source answer, for example `{{ essay.answer }}` if that is consistent with current templating semantics.

## Runtime Behavior

`QuestionSlop` should have a custom invigilator, analogous to `InvigilatorThinking`, but it should call a detector provider instead of `LanguageModel.async_get_response()`.

Behavior:

- Render `question_text` with the current scenario/answers context.
- Send the rendered text to the provider adapter.
- Normalize the provider response into the stable EDSL answer schema.
- Store provider metadata in `raw_model_response` or an equivalent provider-response field if that is the least disruptive path.
- Respect EDSL cache semantics so repeated text/provider/options do not re-call the API.
- Do not use the agent persona, survey-level model, or model pricing path.

Open implementation question: current EDSL result internals expect model-like token/cost metadata. The MVP can set token counts and model costs to `None`/`0`, but should not pretend Pangram is an LLM.

## Answer Schema

The returned answer should be stable even if Pangram changes its raw payload.

```json
{
  "classification": "mixed",
  "headline": "AI Detected",
  "prediction": "We are confident that this document is a mix of AI-generated, AI-assisted, and human-written content",
  "ai_score": 0.70,
  "ai_assisted_score": 0.20,
  "human_score": 0.10,
  "confidence": null,
  "provider": "pangram",
  "provider_model": "3.0",
  "text_length": 742,
  "num_ai_segments": 7,
  "num_ai_assisted_segments": 2,
  "num_human_segments": 1,
  "dashboard_link": null,
  "segments": [
    {
      "text": "This product is a game-changer...",
      "start": 0,
      "end": 36,
      "label": "AI-Generated",
      "ai_assistance_score": 0.91,
      "confidence": "High",
      "word_count": 5,
      "token_length": 6
    }
  ],
  "raw_response": null
}
```

Required normalized fields:

- `classification`: one of `ai`, `ai_assisted`, `human`, `mixed`, `uncertain`, `error`, `too_short`.
- `headline`: provider summary headline when available.
- `prediction`: provider long-form prediction when available.
- `ai_score`: float between 0 and 1, mapped from Pangram `fraction_ai`, or null.
- `ai_assisted_score`: float between 0 and 1, mapped from Pangram `fraction_ai_assisted`, or null.
- `human_score`: float between 0 and 1, mapped from Pangram `fraction_human`, or null.
- `confidence`: normalized document-level confidence when available; Pangram currently exposes window-level confidence.
- `provider`: provider name.
- `provider_model`: provider model/version when available, mapped from Pangram `version`.
- `text_length`: character length of analyzed text.

Optional fields:

- `segments`
- `num_ai_segments`
- `num_ai_assisted_segments`
- `num_human_segments`
- `dashboard_link`
- `raw_response`
- `error_code`
- `error_message`

## Pangram Provider Adapter

Pangram supports both a Python SDK and REST API. The Python SDK package is `pangram-sdk`; the client is `Pangram`; `Pangram(api_key=...)` reads `PANGRAM_API_KEY` if the key is not passed directly. The SDK `predict(text, public_dashboard_link=False, timeout=300, poll_interval=0.5)` submits an async inference task, polls until completion, and returns the completed task payload.

The REST API uses:

- Base URL for AI detection: `https://text.external-api.pangram.com`
- Auth header: `x-api-key: <api-key>`
- Submit task: `POST /task` with JSON body `{"text": "...", "public_dashboard_link": false}`
- Poll task: `GET /task/{task_id}` until `stage` is `STAGE_SUCCESS` or `STAGE_FAILED`
- Bulk submit: `POST /bulk`
- Bulk status: `GET /bulk/{bulk_id}`
- Bulk results: `GET /bulk/{bulk_id}/results?offset=0&limit=100`

For MVP, prefer the SDK if adding `pangram-sdk` is acceptable. Otherwise, implement the small REST flow directly to avoid a new dependency.

Proposed adapter boundary:

```python
class TextDetectionProvider:
    async def score_text(self, request: TextDetectionRequest) -> TextDetectionResult:
        ...
```

`TextDetectionRequest`:

```json
{
  "text": "...",
  "include_segments": true,
  "public_dashboard_link": false,
  "timeout_seconds": 300,
  "poll_interval": 0.5,
  "metadata": {
    "question_name": "review_slop"
  }
}
```

`TextDetectionResult` should already be normalized to the EDSL schema before reaching the invigilator.

Pangram response fields to map:

| Pangram field | EDSL normalized field |
| --- | --- |
| `stage` | provider raw status; error if not `STAGE_SUCCESS` |
| `version` | `provider_model` |
| `headline` | `headline` |
| `prediction` | `prediction` |
| `prediction_short` | `classification` |
| `fraction_ai` | `ai_score` |
| `fraction_ai_assisted` | `ai_assisted_score` |
| `fraction_human` | `human_score` |
| `num_ai_segments` | `num_ai_segments` |
| `num_ai_assisted_segments` | `num_ai_assisted_segments` |
| `num_human_segments` | `num_human_segments` |
| `dashboard_link` | `dashboard_link`, only if requested |
| `windows` | `segments` |
| `windows[].text` | `segments[].text` |
| `windows[].label` | `segments[].label` |
| `windows[].ai_assistance_score` | `segments[].ai_assistance_score` |
| `windows[].confidence` | `segments[].confidence` |
| `windows[].start_index` | `segments[].start` |
| `windows[].end_index` | `segments[].end` |
| `windows[].word_count` | `segments[].word_count` |
| `windows[].token_length` | `segments[].token_length` |

`prediction_short` mapping:

| Pangram `prediction_short` | EDSL `classification` |
| --- | --- |
| `AI` | `ai` |
| `AI-Assisted` | `ai_assisted` |
| `Human` | `human` |
| `Mixed` | `mixed` |
| anything else | `uncertain` |

Credential handling:

- Read API key from `PANGRAM_API_KEY` or EDSL key lookup.
- Never serialize API keys in question objects.
- Do not include API keys or request headers in raw responses.

## Caching

Provider calls should be cacheable by:

- rendered text hash
- provider
- provider model/version if known
- `include_segments`
- `public_dashboard_link`
- adapter version

This avoids paying for repeated detector calls across identical scenarios or reruns.

The cache key should not include the raw API key.

## Error Handling

Provider errors should become structured answers unless the caller asks to raise.

Recommended behavior:

| Condition | Result |
| --- | --- |
| Missing API key | Raise configuration error before run. |
| Short text and `on_short_text="return_null"` | `classification="too_short"`, scores null. |
| Provider timeout | `classification="error"`, `error_code="timeout"`. |
| Rate limit | `classification="error"`, `error_code="rate_limited"`. |
| Insufficient credits | `classification="error"`, `error_code="insufficient_credits"`. |
| Forbidden task access | `classification="error"`, `error_code="forbidden"`. |
| Payload too large | `classification="error"`, `error_code="payload_too_large"`. |
| Invalid input text | `classification="error"`, `error_code="invalid_text"`. |
| Provider 4xx request error | `classification="error"`, include stable code. |
| Provider 5xx | Retry if policy allows, then error answer. |
| Invalid provider JSON | `classification="error"`, `error_code="invalid_provider_response"`. |

The implementation should avoid silently converting provider failures into "human" or low-AI scores.

## Privacy And Safety

Detector scoring can be sensitive and should not be treated as ground truth.

Requirements:

- Document that scores are probabilistic detector outputs, not definitive authorship proof.
- Do not send text to Pangram unless the user intentionally uses `QuestionSlop`.
- Avoid sending hidden agent traits or unrelated survey context. Send only rendered `question_text`.
- Redact raw provider payloads by default.
- Make `include_raw_response=False` the default.
- Consider a warning or explicit opt-in for human respondent data, depending on broader EDSL data-sharing policy.

## Serialization

Example:

```json
{
  "edsl_class_name": "QuestionBase",
  "edsl_version": "x.y.z",
  "question_type": "slop",
  "question_name": "review_slop",
  "question_text": "{{ review_text }}",
  "provider": "pangram",
  "include_segments": true,
  "include_raw_response": false,
  "public_dashboard_link": false,
  "min_text_length": 80,
  "on_short_text": "return_null",
  "timeout_seconds": 300,
  "poll_interval": 0.5
}
```

Like other question types, `QuestionSlop.from_dict()` should remove EDSL metadata and reconstruct the question.

## Implementation Plan

### Phase 1: Local Shape

- Add `edsl/questions/question_slop.py`.
- Add `QuestionSlop` to `edsl/questions/__init__.py`.
- Register `question_type = "slop"`.
- Define response model/validator for dict answer shape.
- Add serialization tests.
- Add example.

### Phase 2: Provider Abstraction

- Add Pangram provider adapter with injectable HTTP client or SDK wrapper.
- Add fake provider for unit tests.
- Add credential lookup.
- Support `POST /task` plus `GET /task/{task_id}` polling, or SDK `predict()`.
- Normalize provider output to stable schema.
- Add error mapping.

### Phase 3: Invigilator

- Add `InvigilatorSlop`.
- Render `question_text` using normal EDSL context.
- Call provider adapter.
- Return `EDSLResultObjectInput`.
- Preserve cache behavior.

### Phase 4: Integration

- Add docs example.
- Add optional CLI or notebook example for batch scoring.
- Add integration test gated by `PANGRAM_API_KEY`.

## Test Plan

- Constructor defaults are correct.
- Invalid provider is rejected.
- Invalid `on_short_text` is rejected.
- Serialization round-trips.
- Short text returns `too_short` when configured.
- Missing API key raises a configuration error.
- Fake provider response maps to normalized answer.
- Provider timeout maps to error answer.
- Pangram `prediction_short` values map to stable `classification` values.
- Pangram `windows` map to `segments`.
- Raw response is omitted by default.
- Raw response is redacted when included.
- Same rendered text hits cache on rerun.
- Survey with `QuestionSlop` works with scenarios.

## Open Questions

- Is `QuestionSlop` the right public name, or should it be a nickname for `QuestionAIDetection`?
- Should the answer be a dict question response or a custom Pydantic response?
- Should detector cost be represented in Results cost columns, or should provider cost live in separate metadata?
- Should this be allowed in humanize surveys, given it sends respondent text to a third-party detector?
- Should the class support scoring prior answers directly, or only rendered `question_text`?
- Should MVP use the `pangram-sdk` dependency or direct REST calls?
- Should EDSL support Pangram Bulk API for large `ScenarioList` runs instead of one task per row?
- What minimum text length should EDSL enforce?
- Should `dashboard_link` ever be included in normal Results, or should it be treated as potentially sensitive?

## References

- Pangram website: https://www.pangram.com/
- Pangram API product page: https://www.pangram.com/solutions/api
- Pangram REST API overview: https://docs.pangram.com/api-reference/introduction
- Pangram REST API quickstart: https://docs.pangram.com/quickstart-rest
- Pangram Python SDK docs: https://docs.pangram.com/sdk/python
- Pangram technical report: https://arxiv.org/abs/2402.14873
