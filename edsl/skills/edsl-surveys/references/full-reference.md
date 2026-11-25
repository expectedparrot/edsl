# Full EDSL survey reference

## Contents

- Basic survey creation and instructions
- Question types and parameters
- Generated images
- Jinja templating and per-item follow-ups
- Survey rules and memory
- Chaining and running surveys
- Quick reference

Consolidated reference for building surveys with EDSL: question types, Jinja2 templating, skip/navigation rules, memory modes, helper utilities, and visualization.

> **Detailed code examples** for question types, templating, rules, and memory are in `references/survey-reference.md`. Consult that file when you need full constructor signatures or worked examples.

## Basic Survey Creation

```python
from edsl import Survey, QuestionFreeText, QuestionMultipleChoice

q1 = QuestionFreeText(question_name="name", question_text="What is your name?")
q2 = QuestionMultipleChoice(
    question_name="color",
    question_text="What is your favorite color?",
    question_options=["Red", "Blue", "Green", "Yellow"]
)
survey = Survey([q1, q2])
```

Survey builder methods **mutate the survey in place and return `self`** — `add_question`, `add_instruction`, `add_rule`, `add_skip_rule`, `add_stop_rule`, `loop_over`, and the memory-mode setters. Assigning the result back is conventional style, but it is not what makes it work:

```python
survey = Survey()
survey = survey.add_question(QuestionFreeText(question_name="q1", question_text="First?"))
survey = survey.add_question(new_question, index=1)  # insert at position
```

Survey mutation is in place: methods such as `add_question()` return the same survey object. Call `.duplicate()` before constructing independent variants.

## Adding Instructions

```python
from edsl import Instruction

survey = survey.add_instruction(
    Instruction(text="Please answer honestly.", name="intro")
)
```

> **IMPORTANT**: `Instruction` text is NOT checked for scenario field references. If your scenarios have fields that must be used, reference them in a **question's `question_text`**, not in an Instruction.

---

## Randomizing Answer-Option Order

To randomize option order per respondent (controls for position bias), use `questions_to_randomize`. This works for any question type that has options (multiple choice, checkbox, rank, top-k, etc.):

```python
survey = Survey(
    questions=[q1, q2],
    questions_to_randomize=["q1"]  # List of question names to randomize
)
```

The `questions_to_randomize` constructor argument accepts the names of option-bearing questions whose option order should be randomized per respondent. Ordered scales and options with meaningful order generally should not be randomized. See `references/survey-reference.md` for examples.

---

## Question Types

All questions require `question_name` (a valid Python identifier) and `question_text`. See `references/survey-reference.md` for full code examples of every type.

```python
from edsl import Question
Question.available()  # list all available types
```

### Question Type Quick Reference

| Type | Use Case | Key Parameter |
|------|----------|---------------|
| `QuestionFreeText` | Open-ended responses | — |
| `QuestionEdit` | Revise supplied text; Humanize shows tracked insertions and deletions | `text_to_edit` |
| `QuestionEmail` | A valid email address | — |
| `QuestionURL` | An absolute URL | — |
| `QuestionMultipleChoice` | Single selection | `question_options` |
| `QuestionCheckBox` | Multiple selections | `question_options`, `min_selections`, `max_selections` |
| `QuestionNumerical` | Numbers | `min_value`, `max_value` |
| `QuestionYesNo` | Binary yes/no | — |
| `QuestionLinearScale` | Numeric scale | `question_options`, `option_labels` |
| `QuestionLikertFive` | 5-point agree/disagree | — |
| `QuestionList` | List of items | `max_list_items` (see `loop_over` for per-item follow-ups) |
| `QuestionRank` | Ordering | `question_options`, `num_selections` |
| `QuestionMatrix` | Grid/table | `question_items`, `question_options` |
| `QuestionCheckboxMatrix` | Multiple selections in each grid row | `question_items`, `question_options`, `min_selections`, `max_selections` |
| `QuestionBudget` | Budget allocation | `question_options`, `budget_sum` |
| `QuestionDemand` | Quantity demanded at each price | `prices` |
| `QuestionDistribution` | Probability over outcomes or numeric intervals | `question_options`, `bins`, or `min_value`/`max_value`/`bucket_size` |
| `QuestionDict` | Key-value pairs | `answer_keys` |
| `QuestionExtract` | Extract from text | `answer_template` |
| `QuestionDropdown` | Large option sets (BM25 search) | `question_options` |
| `QuestionMultipleChoiceWithOther` | MC + freeform "Other" | `question_options`, `other_option_text` |
| `QuestionCheckBoxWithOther` | Checkbox + freeform "Other" | `question_options`, `other_option_text` |
| `QuestionTopK` | Select top K items | `question_options`, `k` |
| `QuestionInterview` | Multi-turn interview (humanize) | `interview_guide` |
| `QuestionFileUpload` | File upload from respondent (humanize only) | — |
| `QuestionImageGeneration` | Generate an image — the answer is an image `FileStore` | `model`, `service_name` |
| `QuestionFunctional` | Local Python computation (no LLM) | `func` |
| `QuestionPydantic` | Pydantic model response schema | `pydantic_model` |
| `QuestionMarkdown` | Markdown-formatted response | — |

### Common Parameters

| Parameter | Description |
|-----------|-------------|
| `question_name` | Unique identifier (valid Python identifier) |
| `question_text` | The question text (supports Jinja2 templating) |
| `answering_instructions` | Optional custom instructions for the LLM |
| `question_presentation` | Optional custom presentation template |

---

## Per-question model + system prompt (`thinking_question`)

`thinking_question()` wraps an existing question so that — at run time — it uses **its own model** and **its own system prompt**, independent of the survey-level model and the agent persona. Everything else is preserved: the question's type, options, answering instructions, and response validation.

### When to use it

Reach for it when **one question in a survey should run on a different model or system prompt than the survey around it**, while still slotting back in as a validated answer that later questions can pipe from:

- **Persona-free steps inside a persona-driven survey.** The agent has a persona for the opinion questions, but one step is really mechanical — classify this text, extract a figure, summarize prior answers, score against a rubric. Swap the persona for a neutral, task-specific system prompt so that step stays objective.
- **LLM-as-judge / grading questions.** One question needs a strict rubric or instruction set that would be wrong as a survey-wide system prompt.
- **Model heterogeneity within one survey.** Most questions run on a cheap/fast model, but one hard reasoning question needs a stronger one (or the reverse) — without changing the survey-level model.
- **Human surveys: an invisible server-side step** whose answer is piped into the next question the respondent sees — see `edsl:edsl-human-survey`.

Where it's the **wrong** tool:
- To change the model for the **whole** survey → use `.by(Model(...))`, don't wrap.
- When you actually want the **persona to answer** (the point of simulation) → don't strip it.

```python
from edsl import Survey, QuestionFreeText, QuestionMultipleChoice
from edsl.questions.question_thinking import thinking_question

# Resolve the model name at plan time — see ep-agent:workflow-model-selection.
# Do not copy a model name from this example; confirm a current one with
# ep models.
CLASSIFIER_MODEL = "<current-model-name>"

# A regular question — answered normally, on the survey's model and agent persona.
review = QuestionFreeText(
    question_name="review",
    question_text="Write a one-sentence review of your last coffee.",
)

# A thinking question — same MC type/options/validation, but pinned to its own
# model and system prompt, ignoring the survey model and any agent persona.
sentiment = thinking_question(
    QuestionMultipleChoice(
        question_name="sentiment",
        question_text="Is this review positive or negative? Review: {{ review.answer }}",
        question_options=["positive", "negative"],
    ),
    model=CLASSIFIER_MODEL,
    system_prompt="You are a meticulous sentiment classifier. Answer literally.",
)

survey = Survey([review, sentiment])
```

`thinking_question(q, model=None, system_prompt="")`:

| Parameter | Description |
|-----------|-------------|
| `q` | Any question instance (multiple choice, free text, checkbox, etc.). |
| `model` | A model name string or a `Model` instance both work. Confirm a current name per `ep-agent:workflow-model-selection`; never hardcode one from memory. |
| `system_prompt` | String that **replaces the agent persona** in the system prompt. Defaults to `""` (empty). |

In a **web (human) survey**, a thinking question runs invisibly server-side and its answer can be piped into a later question the respondent sees — see `edsl:edsl-human-survey`.

---

## Generated images (`QuestionImageGeneration`)

`QuestionImageGeneration` produces an **image** as its answer — a `FileStore` — rather than text. Its `question_text` is not a question anyone reads: it is the **generation prompt**, Jinja-rendered against the scenario and prior answers like any other question text.

```python
from edsl import QuestionImageGeneration, Survey

visual = QuestionImageGeneration(
    question_name="concept_visual",
    question_text="A product photo of {{ scenario.product }} on a kitchen counter, warm morning light.",
)
```

| Parameter | Description |
|---|---|
| `question_text` | The generation prompt. Supports `{{ scenario.key }}` and `{{ q_name.answer }}` piping. |
| `model` | Image model. Default `"gemini-3.1-flash-image"`. |
| `service_name` | Provider. `"google"` is the default and the only supported provider — leave it alone. |
| `generation_parameters` | **Ignore this.** The constructor accepts extra provider kwargs (loose or in this dict), but they do not reliably reach the provider today. Leave it unset and put everything you want in the prompt. |

The image model is named **on the question**, so `.by(Model(...))` does not control it — a survey's language model and this question's image model are set separately. Image generation goes through Google only; do not point `service_name` at another provider, and do not offer the user a choice of provider.

**Referenced images become input images.** If the prompt references a scenario field or a prior answer that holds an image `FileStore`, that image is sent to the provider *as an image* rather than stringified into the prompt — which is how you get editing and style-transfer behavior instead of a description-only generation:

```python
edit = QuestionImageGeneration(
    question_name="restyled",
    question_text="Redraw {{ scenario.logo }} in a flat monochrome style, keeping the shape.",
)

from_upload = QuestionImageGeneration(
    question_name="staged",
    question_text="Place the room in {{ room_photo.answer }} under evening light.",
)
```

In a **web (human) survey** an image generation question runs invisibly server-side, like a thinking question, and the respondent can be shown the result by piping `{{ q_name.answer }}` into a later question — see `edsl:edsl-human-survey`. Generation is billed to the survey owner (`edsl:edsl-surveys-cost`).

---

## Jinja2 Templating in Questions

EDSL uses Jinja2 templating for dynamic questions. Template variables are enclosed in `{{ }}`.

### Template Variables Reference

| Variable | Access Pattern | Example | Context |
|----------|---------------|---------|---------|
| Scenario value | `{{ scenario.key }}` | `{{ scenario.fruit }}` | In `question_text` or `question_options` |
| Agent trait | `{{ agent.trait }}` | `{{ agent.occupation }}` | In `question_text` |
| Prior answer | `{{ question_name.answer }}` | `{{ q1.answer }}` | In `question_text` (piping) |
| Prior answer | `{{ question_name.answer }}` | `{{ features.answer }}` | In `question_options` (dynamic options) |
| Prior answer | `{{ question_name.answer }}` | `{{ products.answer }}` | In `question_items` (matrix rows) |

Templating works in `question_text`, `question_options`, and `question_items`. See `references/survey-reference.md` for worked examples of scenario templating, agent templating, piping, option templating, and using prior answers as dynamic options.

### Piping requires prior question context

When you pipe a prior answer into a follow-up question, the answering LLM only sees the resolved text — it has **no memory** of the original question or its options. You must restate that context in the follow-up question text so the answer is interpretable.

**Bad** — the LLM sees "You said Option B" with no idea what the question was:
```python
"Why did you choose {{ q1.answer }}?"
```

**Good** — the LLM knows what was asked and what it answered:
```python
"You were previously asked 'Which product do you prefer: Widget A, Widget B, or Widget C?' and you said '{{ q1.answer }}'. Why did you make that choice?"
```

This applies any time the piped answer would be ambiguous without context (e.g., a scale value, an option label, or a short phrase). If the answer is inherently self-explanatory (e.g., a cuisine name used as `"What is your favorite {{ favorite_cuisine.answer }} dish?"`), restating the original question is not necessary.

### Jinja if/then for per-answer wording (e.g. translations)

`{% if %}` / `{% elif %}` / `{% else %}` blocks in `question_text` let a single question change its wording based on a prior answer — the clean way to handle **multi-language surveys** and other per-answer variants for **structured** questions. Ask the choice once, then branch each downstream question's text on it. Do **not** duplicate structured questions and route with skip logic for this; one question with an if/then body keeps results in a single column per question.

**Exception — `QuestionInterview`:** interview language is set in humanize schema (`text_interview_config.language` / `voice_interview_config.language`), not in `question_text`, so Jinja cannot select it. When a prior answer chooses the interview language, fork into one `QuestionInterview` per language and skip-route — see **edsl:edsl-human-survey** (`references/interview-languages.md`).

```python
q_language = QuestionMultipleChoice(
    question_name="language",
    question_text="Which language would you like to complete this survey in?",
    question_options=["English", "Spanish", "French"],
)

q_satisfaction = QuestionLinearScale(
    question_name="satisfaction",
    question_text="""
{% if language.answer == 'Spanish' %}
En una escala del 1 al 5, ¿qué tan satisfecho está con nuestro servicio?
{% elif language.answer == 'French' %}
Sur une échelle de 1 à 5, quel est votre niveau de satisfaction avec notre service ?
{% else %}
On a scale of 1 to 5, how satisfied are you with our service?
{% endif %}
""".strip(),
    question_options=[1, 2, 3, 4, 5],
)

survey = Survey([q_language, q_satisfaction])
```

EDSL detects the variable inside the `{% if %}` and pipes the prior answer in, so this renders correctly in both `.run()` and humanize. Two things to get right:
- Reference an **existing prior** `question_name` exactly — a typo (`langauge.answer`) is treated as undefined, silently evaluates falsy, and falls through to `{% else %}` with no error (see **edsl:edsl-quirks**).
- Always include an `{% else %}` for the default language so a fall-through is intentional.
- Keep answer values language-neutral (numeric scale points, shared option codes) so responses stay comparable across languages; translate only the displayed text.

---

## Per-item follow-ups: `Survey.loop_over`

Piping asks **one** question about a whole list answer. To ask a **block of questions once per item** of a list the respondent supplies at run time, use `survey.loop_over(source_q, ask=[...], max_items=N)` — not a two-pass design feeding one survey's answers into a second as scenarios.

`max_items` is a hard ceiling (default 10) and items beyond it are silently dropped, so pair it with the source question's `max_list_items` to avoid truncating valid list answers. Note also that every iteration yields a column whether or not it was asked, so cost estimates count all `max_items` copies (see **edsl:edsl-surveys-cost**).

Distinct from `Question.loop(scenario_list)`, which expands a list *you* already know at design time. See `references/survey-reference.md` for the full reference — worked examples, per-iteration `skip_when`/`jump_when`, naming scheme, and constraints.

---

## Survey Rules and Flow Control

Rules define conditional navigation through surveys using Jinja2 template expressions.

| Task | Method |
|------|--------|
| Skip a question | `survey.add_skip_rule(question, expression)` |
| Navigate to question | `survey.add_rule(question, expression, next_question)` |
| Stop early | `survey.add_stop_rule(question, expression)` |
| Set priority | `survey.add_rule(q, expr, next_q, priority=1)` |
| View rules | `survey.show_rules()` |
| Jump to end | `survey.add_rule(q, expr, EndOfSurvey)` |

Expression syntax: `"{{ question_name.answer }} == 'value'"`, `"{{ age.answer }} > 18"`, compound with `and`/`or`.

`EndOfSurvey` import: `from edsl.surveys import EndOfSurvey`

See `references/survey-reference.md` for full code examples.

---

## Survey Memory System

Memory controls which previous question-answer pairs an agent sees when answering each question.

> **HUMANIZE:** Survey memory APIs apply only to LLM agent runs (`.run()`). Human surveys deployed via `.humanize()` do not use them — pipe prior answers with `{{ q_name.answer }}` instead. See **edsl:edsl-human-survey** — "Memory and piping".

> **IMPORTANT FOR IMAGE SCENARIOS:** If your scenarios include images (via `{{ scenario.image }}`), you must include that template variable in **every question** that needs the image — the LLM has no memory of images from prior questions. Do **not** use memory modes to work around this. Just pass `{{ scenario.image }}` in each question's `question_text`. Memory modes only provide prior question-answer pairs, not scenario content.

### Memory modes

| Mode | Method | When to use |
|------|--------|-------------|
| No memory | (default) | Questions measure independent constructs — use this unless you have a specific reason not to |
| Piping | `{{ q_name.answer }}` in `question_text` | One or two specific prior answers are needed — **preferred over memory modes** |
| Targeted | `survey.add_targeted_memory(focal_q, prior_q)` | A specific question needs context from one specific prior question, and piping is impractical |
| Memory collection | `survey.add_memory_collection(focal_q, [prior_qs])` | A specific question needs context from several specific prior questions |
| Lagged | `survey.set_lagged_memory(lags=N)` | Rolling conversational context — each question sees only the N most recent exchanges |
| Full memory | `survey.set_full_memory_mode()` | True interview/dialogue where every prior exchange is genuinely relevant |

**Do not apply `set_full_memory_mode()` as a default.** It increases token cost proportionally to survey length, introduces carry-over bias, and creates unintended order effects. See `references/survey-reference.md` for the full decision guide, cost warnings, and documentation requirements.


---

## Chaining Operations

Survey methods can be chained since each returns the survey itself (chaining mutates it — see "Basic Survey Creation" above):

```python
survey = (Survey([q1, q2, q3])
    .add_rule("q1", "{{ q1.answer }} == 'skip'", "q3")
    .add_skip_rule("q2", "{{ q1.answer }} == 'skip'")
    .add_question(q4))
```

## Running a survey — labeling the job

Use `ep run` as the complete inference-and-persistence operation. Build the
survey, agents, scenarios, models, and `jobs.ep` in study files, then run:

```bash
ep run edsl_jobs/job_a/jobs.ep \
  --remote_inference_description "<descriptive run label>" \
  --results_description "<same descriptive run label>" \
  --output data/results.ep
```

After a run, inspect completion status and saved Results with EDSL CLI commands such as:

```bash
ep results summary data/results.ep
ep results columns --file data/results.ep
ep results head data/results.ep --rows 5
```

For reproducible study runs, save survey, scenario list, agent list, and model list as `.ep` files, build `jobs.ep`, then run the job through the EDSL CLI:

```bash
ep jobs build \
  --survey edsl_jobs/job_a/survey.ep \
  --scenarios edsl_jobs/job_a/scenario_list.ep \
  --agents edsl_jobs/job_a/agent_list.ep \
  --models edsl_jobs/job_a/model_list.ep \
  --output edsl_jobs/job_a/jobs.ep

ep run edsl_jobs/job_a/jobs.ep \
  --remote_inference_description "Policy support - UBI carbon tax - 150 agents" \
  --results_description "Policy support - UBI carbon tax - 150 agents" \
  --output data/results.ep
```

`remote_inference_description` and `results_description` are optional labels for the remote job and saved Results object. Matching values make it easier to associate the two artifacts.

## Survey Quick Reference

| Task | Method |
|------|--------|
| Create survey | `Survey([q1, q2, q3])` |
| Run with labels | `ep run edsl_jobs/job_a/jobs.ep --remote_inference_description "..." --results_description "..." --output data/results.ep` |
| Add question | `survey.add_question(q, index=None)` |
| Add instruction | `survey.add_instruction(inst)` |
| Generate an image as an answer | `QuestionImageGeneration(question_name="...", question_text="<prompt>")` |
| Run one question on its own model + system prompt | `thinking_question(q, model=..., system_prompt="...")` |
| Ask a block once per item of a list answer | `survey.loop_over(source_q, ask=[...], max_items=N)` |
| Loop a known list at design time | `question.loop(scenario_list)` |
| Get question | `survey.get("question_name")` |
| List questions | `survey.questions` |
| Question names | `survey.question_names` |
| Number of questions | `len(survey)` |
