# Ferrara (2026), *A Practitioner's Guide to Using LLMs in Economic History* — done in EDSL

**Source:** Andreas Ferrara, "A Practitioner's Guide to Using Large Language Models and Generative AI in Economic History," NBER Working Paper No. 35374, June 2026.

**Target:** EDSL (Expected Parrot Domain-Specific Language), the Python package in this repository.

## The point

The guide describes what an economic historian *does* with an LLM — turn a source into a measure, at scale, reproducibly, defensibly — and then recommends a pile of practices to do it well. It assumes the reader will assemble that workflow by hand: type into a chat window, write a Python loop over the API, hand-roll a JSON parser, keep a folder of prompts and outputs for the replication package, remember to pin the model version, remember to archive the raw outputs.

**EDSL is the tool you use to do all of it in one object.** The guide's "API-at-scale" mode *is* EDSL. Every one of its four worked examples is a short EDSL script. And because the workflow is a declarative `Survey × Agents × Scenarios × Models` object rather than a hand-written loop, most of the guide's best practices aren't things you *remember to do* — they're things you *get by running the job*: structured/validated output, a justification on every answer, exact model pinning, archived raw outputs with deterministic replay, cost projection, a shareable replication bundle.

The rest of this doc shows the guide's four worked examples as EDSL code, then shows how running them in EDSL delivers the guide's best practices for free.

---

## The four worked examples, in EDSL

### Example 1 — Emotion in paintings (§2.2)

The guide's headline demo: classify eight (in the real study, 630,000) paintings into eight emotions with a vision model, no ML expertise required. In EDSL that is a multimodal `Scenario` per image, one `QuestionMultipleChoice`, and a vision `Model`:

```python
from edsl import QuestionMultipleChoice, ScenarioList, Scenario, Model

q = QuestionMultipleChoice(
    question_name="emotion",
    question_text="Which single emotion does this painting most express? {{ painting }}",
    question_options=["contentment", "amusement", "excitement", "awe",
                      "fear", "anger", "sadness", "disgust"],
    # include_comment=True is the DEFAULT → every answer carries a one-line justification
)

paintings = ScenarioList.from_directory("paintings/", key_name="painting")   # 8 or 630,000 images

results = q.by(paintings).by(Model("gpt-4o")).run()
results.select("painting", "emotion", "emotion_comment").to_pandas()
```

- The guide ran GPT-4o *and* CLIP to compare. In EDSL you run several models at once and compare in the same `Results`: `q.by(paintings).by([Model("gpt-4o"), Model("claude-opus-4-8")]).run()`.
- The guide's `$0.04` cost check before scaling to 630k → `q.by(paintings).by(Model("gpt-4o")).estimate_job_cost()`.

### Example 2 — Name-blind census linking (§4.2)

The guide gives the model two census records (everything *except* names) and asks whether they are the same person. That is one `Scenario` per candidate pair and a `QuestionYesNo`:

```python
from edsl import QuestionYesNo, ScenarioList, Model

link = QuestionYesNo(
    question_name="same_person",
    question_text="""Two 1900 and 1910 census records (names withheld):
1900: {{ rec_1900 }}
1910: {{ rec_1910 }}
Are these the same person? Explain which fields drove your judgment.""",
)

pairs = ScenarioList.from_csv("candidate_pairs.csv")   # rec_1900, rec_1910 columns
results = link.by(pairs).by(Model("gpt-4o")).run()

# Validate against the IPUMS HIK ground truth the guide used:
results.select("same_person").to_pandas()   # compare to known links → match rate
```

The guide reports the *agentic* Claude Opus 4.8 / GPT-5.5 did best. EDSL's remote-inference and agent layers cover that mode; the `by([...])` sweep is how you'd reproduce the 43–62% comparison across models.

### Example 3 — Anti-Chinese sentiment around the 1882 Exclusion Act (§4.4)

This is the guide's cost-discipline example: 524,458 pages is too expensive, so pre-screen to the 11,011 that mention Chinese people, keep a text window, then send to a batch API. It is also its **cheap-filter → frontier-classifier** chain. In EDSL that is a two-question `Survey` with a skip rule, so the expensive model only runs on pages the cheap model flags:

```python
from edsl import (QuestionYesNo, QuestionLinearScale, Survey,
                  ScenarioList, Model)

relevant = QuestionYesNo(
    question_name="mentions_chinese",
    question_text="Does this snippet discuss Chinese immigrants? {{ snippet }}",
)
hostility = QuestionLinearScale(
    question_name="hostility",
    question_text="Rate the hostility toward Chinese immigrants in: {{ snippet }}",
    question_options=[1, 2, 3, 4, 5],
    option_labels={1: "sympathetic", 5: "hostile"},
)

survey = (Survey([relevant, hostility])
          .add_skip_rule(hostility, "mentions_chinese == 'No'"))   # skip the costly Q

# pre-screen + 30-word window is your preprocessing on the ScenarioList:
pages = ScenarioList.from_csv("chinese_snippets_1882.csv")   # already windowed to ±30 words

results = survey.by(pages).run()   # remote/batch execution handles the 11k pages
```

The guide's model-chaining ("cheap model for high recall, frontier model for precision") maps to running `mentions_chinese` on a cheap model and `hostility` on a frontier model in the same survey.

### Example 4 — Emotional intensity of FDR's wartime speeches (§4.5)

One `Scenario` per speech, a `QuestionLinearScale` for intensity — the "Day of Infamy" address scoring highest:

```python
from edsl import QuestionLinearScale, ScenarioList, Model

intensity = QuestionLinearScale(
    question_name="intensity",
    question_text="Rate the emotional intensity of this speech's delivery: {{ speech }}",
    question_options=[1, 2, 3, 4, 5, 6, 7],
)
speeches = ScenarioList.from_directory("fdr_speeches/", key_name="speech")
results = intensity.by(speeches).by(Model("gpt-4o")).run()
```

(For the guide's *audio* delivery signal, the same pattern takes an `mp4`/audio `FileStore` scenario instead of a text one — EDSL's file handlers cover audio, image, PDF, and Office docs.)

---

## The best practices you get by running the job in EDSL

The guide's Table 2 is a checklist of things to remember. In EDSL, most of them are the behavior you get from the objects above — not extra discipline, but the default.

| Guide recommendation | How EDSL delivers it *while you run the example* |
|---|---|
| **Structured output** ("essential… eliminates parsing failures") | The whole reason to use a question *type*. `QuestionMultipleChoice` constrains the answer to a `Literal` of your options; a `fix()` cascade repairs malformed answers before failing (`questions/question_multiple_choice.py`). You never write a parser. |
| **Rubric with an "uncertain / none" escape option** | `QuestionMultipleChoiceWithOther` auto-appends an "Other:" free-text option; `permissive=True` relaxes the constraint (`questions/question_multiple_choice_with_other.py`). |
| **Ask for a justification** (but not self-rated confidence) | `include_comment=True` is the **default** — every emotion/link/hostility answer above comes with a `*_comment` explaining it (`questions/question_base.py:473`). For the token-probability route the guide prefers over self-rated confidence, `logprobs`/`top_logprobs` are model parameters. |
| **Match model to task** (vision, tier, reasoning) | `Model("gpt-4o")` picks any of 17 providers; multimodal inputs are `FileStore` scenarios; reasoning effort / thinking budget are model params. |
| **Choose the model by error rate, not price** | `by([modelA, modelB, ...])` runs the cross-product in one `Results`; comparing tiers on a validation sample is a `Results` filter, not a manual re-run. |
| **Cheap-filter → frontier-classifier chain** | A two-question `Survey` with `add_skip_rule` (Example 3): the expensive question only fires on flagged rows. |
| **Project cost on a sample before scaling** | `job.estimate_job_cost()` returns token counts + USD from live prices (`jobs/jobs_pricing_estimation.py`) — the guide's `$0.04 → $2,290` projection, built in. |
| **One clean task per context; start fresh** | Enforced by construction: every interview is an isolated, stateless call (`jobs/async_interview_runner.py`). No conversation drift to manage. |
| **Pin the exact model identifier + settings** | The model string is passed through verbatim (`Model("gpt-4o-2024-05-13")`); model + service + params are stored on **every** `Result` (`results/result.py`, `language_models/language_model.py` `to_dict`). |
| **Archive the raw outputs** ("the single most important step") | EDSL's **cache is that archive**: full output keyed on `{model}{params}{prompts}{iteration}` (`caching/cache_entry.py:139`); `raw_model_response` retained per `Result`. Re-running hits the cache and reproduces the numbers exactly — deterministic replay without depending on the provider. |
| **Compare to hand-coded / human data** | `Result.score_with_answer_key(key)` scores against a ground truth (Examples 2's HIK links); `Survey.humanize()` runs the *identical* survey against human respondents via Coop/Prolific, then `Results.compare()`. |
| **Robustness across prompts / models / output types** | The cross-product design *is* this diagnostic: re-run with a `ModelList`, prompt variants, and different question types (yes/no vs. linear scale vs. numerical = binary/discrete/continuous versions of the measure). |
| **Ship prompts, code, outputs, validation data** | `job.show_prompts()` prints the exact prompt; `push()` uploads one `Results`-with-cache object (survey + prompts + model + params + raw outputs) as a shareable replication artifact (`base/base_class.py:138`). The `Survey` object *is* the code. |

---

## The two things you still do outside EDSL — and how EDSL feeds them

EDSL runs the middle of the guide. Two bookends stay with the researcher, exactly where the guide says they belong — and EDSL produces their inputs:

1. **The "is an LLM even the right tool" judgment (§3.1.1)** — literature search, fact lookup, geocoding, causal design. EDSL is infrastructure and enforces no guardrail here; that call is yours. (It does help you *test* feasibility: run a small validation `ScenarioList` and score it before committing.)

2. **The econometric bias correction (§3.3.4–3.3.5)** — treating the measure as a non-classical noisy proxy and correcting the regression (ValidMLInference), or the GABRIEL content-vs-context word-removal test. That lives in downstream stats code. But EDSL generates precisely its two inputs: the LLM-measure `Results` *and* the hand-coded validation `Results` (via `humanize()` or a scored key). The word-removal test is a second EDSL run on a scenario list with the attribute words stripped, compared with `Results.compare()`.

## One thing to set explicitly

The guide says use `temperature=0`. EDSL defaults to **0.5** and buys reproducibility from the cache instead of from temperature. If you want the guide's belt-and-suspenders behavior, pass `temperature=0` on your `Model` *and* keep the cache. (Reasoning models that reject non-1 temperatures are already handled — `open_ai_service.py:54`.)

## Also worth knowing before you send licensed data

The guide's §3.1.2 warning applies directly: by default EDSL can route jobs through Expected Parrot's remote-inference server and sync prompts/responses to a universal remote cache — both move data off your machine. For IPUMS full-count names, ProQuest, newspapers.com, etc., disable remote inference/cache, use your own keys, or run a **local open-weight model via the Ollama provider** so the data never leave your environment — the guide's self-hosting route.

---

*Generated by mapping the workflow and worked examples of Ferrara (2026), NBER WP 35374, onto the EDSL source tree in this repository. Code sketches use EDSL's public API; file references reflect the tree at the time of writing.*
