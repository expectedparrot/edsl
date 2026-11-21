# Invisible background questions in humanized surveys

Most questions in a humanized (web) survey are meant for the **respondent**. A
**thinking question** is not — it runs **behind the scenes** and the respondent never
sees it, but its answer becomes available to later questions. A thinking question is an
AI inference step (`thinking_question`-wrapped, see `edsl:edsl-surveys` for the wrapper
API).

When the survey advances, thinking questions are run automatically and their answers
recorded, and the respondent is taken straight to the next question that actually needs
their input. This is the "auto-advance" behavior: the survey walks forward past every
thinking question, running each one, until it lands on the next human-input question,
instruction, or the end of the survey.

`QuestionImageGeneration` rides the same auto-advance path — see "Image generation as a
background question" below.

## Contents

- Why this is useful
- Worked example — classify silently, then ask a tailored follow-up
- Worked example — upload an image, analyze it, then interview about it
- Image generation as a background question
- Cost
- Notes and limitations
- When a background question fails — debugging with `ep humanize background`, what
  each error kind means, and raising the output token limit

## Why this is useful

Because a thinking question's answer is stored like any other answer, you can **pipe it
into a later question the respondent sees** with `{{ q_name.answer }}`. That lets you
compute or reason about something invisibly and then present a tailored follow-up to the
human.

Typical patterns:

- Classify a free-text answer, then branch or personalize the next visible question
  based on the class.
- Summarize several prior answers into one string, then show it back for confirmation.

## Worked example — classify silently, then ask a tailored follow-up

```python
from edsl import Survey, QuestionFreeText, QuestionMultipleChoice
from edsl.questions.question_thinking import thinking_question

# Placeholder — resolve to a current model name per ep-agent:workflow-model-selection.
CLASSIFIER_MODEL = "<model-name>"

# 1. Visible: the respondent describes an issue in their own words.
complaint = QuestionFreeText(
    question_name="complaint",
    question_text="In your own words, what went wrong with your order?",
)

# 2. Thinking (invisible): silently classify the complaint. The respondent
#    never sees this question — it runs on its own model + system prompt.
classify = thinking_question(
    QuestionMultipleChoice(
        question_name="issue_type",
        question_text=(
            "Classify this customer complaint into one category.\n\n"
            "Complaint: {{ complaint.answer }}"
        ),
        question_options=["shipping", "billing", "product_quality", "other"],
    ),
    model=CLASSIFIER_MODEL,   # a current model; see ep-agent:workflow-model-selection
    system_prompt="You are a support-ticket classifier. Answer with the single best category.",
)

# 3. Visible: a follow-up tailored to the silent classification.
followup = QuestionFreeText(
    question_name="followup",
    question_text=(
        "Thanks. Since this looks like a {{ issue_type.answer }} issue, "
        "what outcome would resolve it for you?"
    ),
)

survey = Survey([complaint, classify, followup])
info = survey.humanize(human_survey_name="Support Intake")
```

The respondent answers `complaint`, then goes **straight to** `followup` — they never
see `issue_type`. Between the two, the server runs the thinking question and pipes its
answer into the follow-up text.

## Worked example — upload an image, analyze it, then interview about it

A thinking question can read an **uploaded file** — including an image: when a
`QuestionFileUpload` answer is piped into it, the uploaded file is attached to the
thinking question's model. That enables a three-step flow — collect an image,
analyze it invisibly with a multimodal model, then hand the analysis to a
`QuestionInterview` so the AI interviewer can probe the respondent about what's actually
in their image.

```python
from edsl import (
    Survey,
    QuestionFileUpload,
    QuestionMultipleChoice,
    QuestionInterview,
)
from edsl.questions.question_thinking import thinking_question

# Placeholder — resolve to a current model name per ep-agent:workflow-model-selection.
CLASSIFIER_MODEL = "<model-name>"

# 1. Visible: the respondent uploads a screenshot of their landing page.
upload = QuestionFileUpload(
    question_name="screenshot",
    question_text="Upload a screenshot of your product's landing page.",
)

# 2. Thinking (invisible): analyze the uploaded image with a multimodal model.
#    Piping the file-upload answer attaches the actual image to this question's
#    model, so it can look at the design and pick the weakest element.
analysis = thinking_question(
    QuestionMultipleChoice(
        question_name="weakest_element",
        question_text=(
            "Look at the attached landing-page screenshot and identify the single "
            "element that most undermines conversion.\n\n{{ screenshot.answer }}"
        ),
        question_options=["headline", "call_to_action", "imagery", "layout", "trust_signals"],
    ),
    model=CLASSIFIER_MODEL,   # a current model; see ep-agent:workflow-model-selection
    system_prompt="You are a critical conversion-rate optimizer. Judge the design, not the copy alone.",
)

# 3. Visible: an AI interview that probes the respondent about that weak element.
#    The interview_guide sees the invisible analysis via piping.
probe = QuestionInterview(
    question_name="probe",
    question_text="Probe the respondent on the weak element of their landing page.",
    interview_guide=(
        "Your goal is to pressure-test the respondent's landing page. An analysis of "
        "their screenshot flagged the '{{ weakest_element.answer }}' as the weakest "
        "element. Open there: ask what they intended it to accomplish, why it looks the "
        "way it does, and what they've tried. Only then move on to other concerns. Keep "
        "it conversational."
    ),
)

survey = Survey([upload, analysis, probe])  # `analysis` runs between the two, unseen
info = survey.humanize(human_survey_name="Landing Page Review")
```

## Image generation as a background question

`QuestionImageGeneration` is the other background question type. It runs in the same
invisible slot as a thinking question, but instead of text its answer is an image
`FileStore`, which you show the respondent by piping it into a later visible question.
Its `question_text` is the **generation prompt**, not something anyone reads.

That gives a web survey a generate-then-react loop: collect something from the
respondent, generate an image from it, then ask them about the result.

```python
from edsl import (
    Survey,
    QuestionFileUpload,
    QuestionImageGeneration,
    QuestionFreeText,
)

# 1. Visible: the respondent uploads a photo of the room they want to redo.
upload = QuestionFileUpload(
    question_name="room_photo",
    question_text="Upload a photo of the room you'd like to redesign.",
)

# 2. Image generation (invisible): the uploaded photo is piped in, so it is sent
#    to the provider as an input image and the generation edits it rather than
#    inventing a new room.
redesign = QuestionImageGeneration(
    question_name="redesign",
    question_text=(
        "Restyle this room in warm mid-century modern, keeping the layout and "
        "windows: {{ room_photo.answer }}"
    ),
)

# 3. Visible: the generated image is piped back for the respondent to react to.
reaction = QuestionFreeText(
    question_name="reaction",
    question_text="Here's one take on your room: {{ redesign.answer }}\n\nWhat works, and what doesn't?",
)

survey = Survey([upload, redesign, reaction])
info = survey.humanize(
    human_survey_name="Room Redesign Concepts",
    humanize_schema={
        "questions": {
            "room_photo": {
                "submitting_indicator": {"type": "callout", "title": "Rendering your room…"},
            }
        }
    },
)
```

Notes specific to image generation:

- **Respondents wait, and the wait is long.** Generation takes far longer than a text
  inference and is cut off after about three minutes; if the one automatic retry is cut
  off too, the respondent can't continue (see "When a background question fails").
  Keep a single generation between two visible questions rather than chaining several.
- **Input images come from piping.** A scenario image or a prior `QuestionFileUpload`
  answer referenced in the prompt is attached as a real input image. An image not
  referenced in the prompt is not sent.

## Cost

Thinking questions **incur AI inference cost**, billed to the **survey owner's** Expected
Parrot balance as a background charge per response. Image generation questions are billed
the same way, against the image model's own pricing. See `edsl:edsl-surveys-cost`.

While the owner's balance is empty, new respondents can't start the survey (they see
"This survey is temporarily unavailable"). A respondent already partway through is
stopped at the next background question, which fails as `insufficient_balance`.

## Notes and limitations

- **No agent persona.** A thinking question runs with its own system prompt in place of
  any persona; that is the point of the wrapper.

## When a background question fails

While a background question runs, the respondent sees a "Working…" screen, then the
next page. A run that fails for a reason a second try could fix (a rate limit, a provider
error, a timeout, a reply cut short) is **retried once automatically**. If that fails
too, or the error isn't one a retry could fix, the respondent sees **"This survey can't
continue right now"**, their answers so far are kept, and they can't go on. Each try is
recorded as a **run**, which is what you inspect to find out what went wrong.

### Debugging: summary → failing runs → one run

When a user reports respondents getting stuck, or asks why a background question isn't
working, read the runs. Start with the summary:

```bash
ep humanize background summary <survey-uuid>
```

It gives the runs `by_status` (`queued`, `running`, `succeeded`, `failed`, `timed_out`,
`abandoned`), the `failures` by error kind, how many runs were `retries`, and
`last_failure_at`, overall and per question under `questions`. That tells you which
question is failing and how.

Then list the failing runs, narrowed to that question:

```bash
ep humanize background runs <survey-uuid> --failed --question classify_feedback
```

Each row has the question, `attempt` (2 is the automatic retry), `status`, `model`,
timestamps, and an `error` with `kind`, `stage`, `message`, `retryable`, and
`http_status` for a provider HTTP error. Then open one run in full:

```bash
ep humanize background run <survey-uuid> <run-uuid>
```

This is where the cause usually shows:

- **`user_prompt`** (and `system_prompt`) — the prompt **after piping**. Check that the
  respondent's earlier answers were substituted as intended: an empty or wrong value
  here means a piping mistake (`{{ q_name.answer }}` naming the wrong question, or one
  the respondent skipped).
- **`generated_tokens`** / **`raw_output`** — what the model actually replied. For
  `parse_error` or `invalid_answer`, compare it with what the question type expects.
- **`files`** — the files sent with the prompt, by `name` and `mime_type`. An image the
  question was meant to see but that isn't listed wasn't referenced in the prompt.
- **`model`**, **`service`**, **`model_parameters`** and token **`usage`**.

Previews are **left out unless `--include-previews`**. When the user is testing through a
preview link, add it, or you'll see no runs. `--response <response-uuid>` narrows to one
respondent. `credits` appears only for the survey's owner.

The same from Python:

```python
from edsl import Coop

coop = Coop()
summary = coop.get_human_survey_background_runs_summary("survey-uuid")
failed = coop.get_all_human_survey_background_runs("survey-uuid", failed_only=True)
run = coop.get_human_survey_background_run("survey-uuid", failed[-1]["uuid"])
```

To show the user the runs in the browser, give them
`coop.get_human_survey_background_runs_url("survey-uuid")` (the survey's **Background
questions** tab).

### Error kinds and what to do

| `error.kind` | What happened | What to do |
|---|---|---|
| `parse_error` | The model's reply couldn't be read as an answer. | Read `generated_tokens`. Tighten the question text or `system_prompt` so the model answers in the expected form, or use a simpler question type (free text). |
| `invalid_answer` | The reply was read but didn't fit the question (an option that doesn't exist, a number out of range). | Same as `parse_error`; check the options or constraints against what the model returned. |
| `provider_incomplete` | The reply was cut short: token limit, content filter, or a refusal (`reason` says which). | Token limit: raise the model's `max_tokens` (see "Raising the output token limit" below) or ask for a shorter answer. Filter or refusal: reword the prompt. |
| `timeout` | No answer within the time limit (about 4 minutes for thinking, 3 for an image). | Use a faster model or lower reasoning effort, or shorten the prompt. |
| `rate_limited` | The provider was busy (HTTP 429). Retried after a wait. | Usually transient. If many runs show it, the survey is busier than the model's limits: try another model. |
| `provider_error` | The provider failed (5xx) or couldn't be reached. | Usually transient. If it persists, try another model or service. |
| `provider_rejected` | The provider refused the request (another 4xx). | Read the prompt and `model_parameters`: an unsupported parameter or input is the usual cause. |
| `provider_auth` | The provider rejected Expected Parrot's credentials (401/403). | Not something the user can fix: report it with the run's `uuid`. |
| `invalid_model` | The question's model can't be run. | Change the question's model to a current one (see `ep-agent:workflow-model-selection`). |
| `insufficient_balance` | The survey owner's balance was empty. | The owner tops up. Respondents already stopped on this stay stopped. |
| `worker_lost` | The run stopped unexpectedly (status `abandoned`). Retried automatically. | Usually nothing. If it repeats, report it with the run's `uuid`. |
| `internal` | Something failed on Expected Parrot's side; `message` includes a reference. | Report it with that reference. For an image question at stage `persisting`, the image was generated but couldn't be stored. |

`stage` says where it failed: `rendering` (building the prompt), `provider_call`,
`validating` (reading the reply) or `persisting` (saving the answer). A failed run is
still charged for what the model consumed, so `credits` can be non-zero.

### Raising the output token limit

A thinking question asking for something long (a recipe, a report, a full map) can hit
its model's output token limit: the run fails with `provider_incomplete` and a token
limit `reason`. Pass `max_tokens` to `Model(...)` and give that model to
`thinking_question`. It's the same on every service; EDSL passes it on under the name
each provider's API expects (`max_tokens` is also accepted for Google, whose own name
is `maxOutputTokens`).

```python
from edsl import Model, QuestionFreeText
from edsl.questions.question_thinking import thinking_question

# Placeholder — resolve to a current model name per ep-agent:workflow-model-selection.
MODEL = "<model-name>"

recipe = thinking_question(
    QuestionFreeText(
        question_name="recipe",
        question_text="Write a full recipe for {{ favorite_food.answer }}.",
    ),
    model=Model(MODEL, max_tokens=4000),
)
```

The default limit differs by service and model, so a question that fits on one model
can be cut off on another. Read it rather than assuming it: `Model(...).parameters`
(`max_tokens`, or `maxOutputTokens` for Google), or a failed run's
`model_parameters`.

On a model that reasons before answering, the reasoning can count against the same
limit, so set it well above the length of the answer you expect.

## Related

- `edsl:edsl-surveys` — the `thinking_question()` wrapper API and `QuestionImageGeneration`.
- `edsl:edsl-surveys-cost` — how background inference is priced and billed.
- `ep-agent:workflow-model-selection` — choosing a current model when one can't be run.
