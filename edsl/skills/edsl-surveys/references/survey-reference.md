# EDSL Survey Reference — Detailed Examples

## Contents

- [Question Type Examples](#question-type-examples) — full code snippets for every EDSL question type
- [Randomizing Answer-Option Order](#randomizing-answer-option-order) — `questions_to_randomize` for any question with options
- [Jinja2 Templating Examples](#jinja2-templating-examples) — scenario, agent, piping, and options templating
- [Looping Follow-Ups Over a List Answer](#looping-follow-ups-over-a-list-answer) — `Survey.loop_over` for per-item question blocks, `skip_when` / `jump_when`, naming scheme
- [Survey Rules Examples](#survey-rules-examples) — skip, navigation, stop rules with code
- [Survey Memory Decision Guide](#survey-memory-decision-guide) — when to use each memory mode, cost/bias warnings, documentation requirements
- [Survey Helper Utilities](#survey-helper-utilities) — matrix combiner and other helpers
- [run() Parameters](#run-parameters) — labeling jobs with `remote_inference_description` and `results_description`
- [Retrieving error reports for failed jobs](#retrieving-error-reports-for-failed-jobs) — `get_error_report_markdown` for debugging remote job failures

---

## Question Type Examples

All questions require `question_name` (a valid Python identifier) and `question_text`.

To see the question types available:

```python
from edsl import Question
Question.available()
```

### QuestionFreeText

Open-ended text responses without constraints.

```python
from edsl import QuestionFreeText

q = QuestionFreeText(
    question_name="feedback",
    question_text="What do you think about our service?"
)
```

### QuestionEdit

Ask a respondent or simulated agent to revise supplied text. The answer is the
complete revised text as a string. In Humanize, respondents edit the text
directly and see insertions and deletions as tracked changes.

```python
from edsl import QuestionEdit

q = QuestionEdit(
    question_name="revise_announcement",
    question_text="Make this clearer while preserving its meaning.",
    text_to_edit="Our product helps teams make better decisions faster.",
)
```

`text_to_edit` can use EDSL piping or scenario templates, so the supplied text
can depend on an earlier answer or scenario value.

### QuestionEmail

An email address. The answer must be a valid email address.

```python
from edsl import QuestionEmail

q = QuestionEmail(
    question_name="contact_email",
    question_text="What email address should we use to follow up?",
)
```

### QuestionURL

A web address. The answer must be an absolute URL, such as
`https://example.com/page`.

```python
from edsl import QuestionURL

q = QuestionURL(
    question_name="portfolio_url",
    question_text="What is the link to your portfolio?",
)
```

### QuestionMultipleChoice

Single selection from a predefined list of options.

```python
from edsl import QuestionMultipleChoice

q = QuestionMultipleChoice(
    question_name="color",
    question_text="What is your favorite color?",
    question_options=["Red", "Blue", "Green", "Yellow"]
)
```

### QuestionCheckBox

Multiple selections from a predefined list (checkbox-style).

```python
from edsl import QuestionCheckBox

q = QuestionCheckBox(
    question_name="features",
    question_text="Which features do you use? (Select all that apply)",
    question_options=["Feature A", "Feature B", "Feature C", "Feature D"],
    min_selections=1,
    max_selections=3
)
```

### QuestionNumerical

Numeric responses with optional min/max bounds.

```python
from edsl import QuestionNumerical

q = QuestionNumerical(
    question_name="age",
    question_text="How old are you?",
    min_value=0,
    max_value=120
)
```

### QuestionYesNo

Simple binary yes/no question (derived from MultipleChoice).

```python
from edsl import QuestionYesNo

q = QuestionYesNo(
    question_name="consent",
    question_text="Do you agree to participate in this survey?"
)
# Options are automatically ["Yes", "No"]
```

### QuestionLinearScale

Linear scale with customizable range and endpoint labels.

```python
from edsl import QuestionLinearScale

q = QuestionLinearScale(
    question_name="satisfaction",
    question_text="How satisfied are you with our service?",
    question_options=[1, 2, 3, 4, 5],
    option_labels={1: "Very Unsatisfied", 5: "Very Satisfied"}
)
```

### QuestionLikertFive

Standard 5-point Likert scale (agree/disagree).

```python
from edsl import QuestionLikertFive

q = QuestionLikertFive(
    question_name="statement_agree",
    question_text="I find the product easy to use."
)
# Options: Strongly disagree, Disagree, Neutral, Agree, Strongly agree
```

### QuestionList

Response as a list of items.

```python
from edsl import QuestionList

q = QuestionList(
    question_name="top_movies",
    question_text="List your top 3 favorite movies.",
    max_list_items=3
)
```

### QuestionRank

Ranking/ordering items by preference.

```python
from edsl import QuestionRank

q = QuestionRank(
    question_name="priority",
    question_text="Rank these features by importance (1 = most important):",
    question_options=["Speed", "Security", "Price", "Support"],
    num_selections=4
)
```

### QuestionMatrix

Grid-based responses with rows (items) and columns (options).

```python
from edsl import QuestionMatrix

q = QuestionMatrix(
    question_name="product_ratings",
    question_text="Rate each product on the following attributes:",
    question_items=["Product A", "Product B", "Product C"],
    question_options=["Poor", "Fair", "Good", "Excellent"],
    randomize_items=True,
    items_to_pin=["Product C"],
)
```

`randomize_items=True` randomizes resolved matrix rows separately for each
interview/respondent. `items_to_pin` keeps named rows in their declared
positions—useful for rows such as "Other" or an overall rating. The resolved
row order is recorded with the result under
`question_items.<question_name>_question_items`, so analysis can reconstruct
what each respondent saw. Randomization changes presentation order, not answer
keys. Decide it before fielding and preview pinned positions.

### QuestionCheckboxMatrix

Use a checkbox matrix when each row can have zero or more selected options. The
answer maps each row label to a list of selected option values; selection bounds
apply separately to every row.

```python
from edsl import QuestionCheckboxMatrix

q = QuestionCheckboxMatrix(
    question_name="weekly_activities",
    question_text="Which activities do you do on each day?",
    question_items=["Monday", "Tuesday", "Wednesday"],
    question_options=["Exercise", "Cooking", "Reading"],
    min_selections=0,
    max_selections=2,
    option_labels={"Exercise": "Workout or sport"},
)
```

A response has the form `{"answer": {"Monday": ["Exercise", "Reading"],
"Tuesday": [], "Wednesday": ["Cooking"]}}`. Rows are required and selections
must be declared options unless `permissive=True`.

### Date, datetime, and numerical range questions

`QuestionDate` validates ISO calendar dates and optional inclusive date bounds.
`QuestionDateTime` requires an ISO 8601 timezone offset and can enforce inclusive
datetime bounds. `QuestionNumericalRange` returns both endpoints of an inclusive
interval as a `{ "min": number, "max": number }` object.

```python
from edsl import QuestionDate, QuestionDateTime, QuestionNumericalRange

q_date = QuestionDate(
    question_name="start_date",
    question_text="What date should work begin?",
    min_date="2026-01-01",
    max_date="2026-12-31",
)
q_datetime = QuestionDateTime(
    question_name="appointment",
    question_text="When should the appointment start? Include the timezone.",
    min_datetime="2026-05-20T09:00:00-04:00",
    max_datetime="2026-05-20T17:00:00-04:00",
)
q_range = QuestionNumericalRange(
    question_name="price_range",
    question_text="What price range is acceptable?",
    min_value=0,
    max_value=1000,
)
```

The respective answer values look like `"2026-05-20"`,
`"2026-05-20T14:30:00-04:00"`, and `{"min": 25, "max": 60}`. For date-time
questions, an answer without an offset (for example, `2026-05-20T14:30:00`) is
invalid.

### QuestionBudget

Allocating a fixed budget across multiple options.

```python
from edsl import QuestionBudget

q = QuestionBudget(
    question_name="time_allocation",
    question_text="How would you allocate 100 hours across these activities?",
    question_options=["Work", "Exercise", "Leisure", "Sleep"],
    budget_sum=100
)
```

### QuestionDemand

A demand curve: the quantity the respondent would buy at each price. The answer
is a list of non-negative quantities, one per price, in the order of `prices`.

```python
from edsl import QuestionDemand

q = QuestionDemand(
    question_name="coffee_demand",
    question_text="How many cups of coffee would you buy per week at each price?",
    prices=[1.0, 2.0, 3.0, 4.0],
)
```

### QuestionDistribution

Eliciting a probability distribution over named outcomes or numerical
intervals. The answer is one dictionary mapping every label to a probability,
summing to 1. For intervals, each value is the probability of landing anywhere
in that bin, not a density height.

Supply exactly one of three forms:

```python
from edsl import QuestionDistribution

outcome = QuestionDistribution(
    question_name="launch_outcome",
    question_text="How likely is each outcome for the product launch?",
    question_options=["Exceeds target", "Meets target", "Misses target"],
)
# {"Exceeds target": 0.25, "Meets target": 0.5, "Misses target": 0.25}

commute = QuestionDistribution(
    question_name="commute_minutes",
    question_text="How many minutes will your commute take tomorrow?",
    bins=["[0,15)", "[15,30)", "[30,60)", "[60,Inf)"],
)
# {"[0,15)": 0.1, "[15,30)": 0.6, "[30,60)": 0.25, "[60,Inf)": 0.05}

price = QuestionDistribution(
    question_name="expected_price",
    question_text="What will a gallon of milk cost next year, in dollars (2 to 6)?",
    min_value=2,
    max_value=6,
    bucket_size=1,
)
# price.answer_keys: ("[2,3)", "[3,4)", "[4,5)", "[5,6]")
```

- **Outcomes** must be mutually exclusive and exhaustive; add an explicit
  "Other" option if needed.
- **Explicit bins** allow unequal widths and infinite tails. They must be in
  ascending order with no gaps or overlaps, and exactly one of two adjacent bins
  includes the shared boundary. Finite outer endpoints must be closed.
- **Generated bins** need finite bounds. The last bin is shortened to end at
  `max_value` and includes it.

Answers must include every key (zeros included) with values in [0, 1] summing
to 1 within `tolerance` (default `1e-6`). Values are stored as given, never
normalized. Labels, bins, and bounds are static (no templating), and option
randomization is not supported. Read a single probability in later questions
with `{{ commute_minutes.answer["[15,30)"] }}`.

### QuestionDict

Response as key-value pairs (structured data). `value_types` and
`value_descriptions` are optional, one per key. In Humanize, each key's type
decides its field: a number for `int` and `float`, Yes/No for `bool`, one item
per line for a list, and text otherwise.

In a human survey, unless the researcher asks for a dict, prefer separate
questions (`QuestionNumerical`, `QuestionYesNo`, `QuestionList` and so on)
`edsl:edsl-human-survey` (optional cross-reference: grouped on one page):
each can be optional, can be filled in by the survey assistant, and gets its
own column in the results. A dict labels each field with its key and value
type (`owns_car`, `bool`), so give every key a `value_descriptions` entry if
people will answer it.

Humanize takes `str`, `int`, `float`, `bool` and flat lists of these as value
types. For anything nested, such as `list[list[int]]` or a dict value, people
can't enter a structured answer, so split it into separate keys or questions.

```python
from edsl import QuestionDict

q = QuestionDict(
    question_name="household",
    question_text="Tell us about your household:",
    answer_keys=["adults", "children", "owns_car", "pets"],
    value_types=["int", "int", "bool", "list[str]"],
    value_descriptions=[
        "Number of adults",
        "Number of children",
        "Whether anyone in the household owns a car",
        "Kinds of pets, if any",
    ],
)
```

### QuestionExtract

Extracting specific information from text.

```python
from edsl import QuestionExtract

q = QuestionExtract(
    question_name="entities",
    question_text="Extract all company names from the following text: {{ scenario.text }}",
    answer_template={"companies": "List of company names"}
)
```

### QuestionDropdown

BM25-powered search through large option sets.

```python
from edsl import QuestionDropdown

q = QuestionDropdown(
    question_name="country",
    question_text="Select your country:",
    question_options=["Afghanistan", "Albania", ..., "Zimbabwe"]
)
```

In a Humanize survey, the respondent enters search terms in a combo box, reviews ranked matches, and selects one option. The choice fills the input, and the response is stored as a one-item list. `question_options_details` also contributes to matching when provided.

`top_k` (5 by default) sets how many ranked matches the respondent sees. Respondents must choose a listed option, and the answer is that option's text.

### QuestionMultipleChoiceWithOther

Multiple choice with an "Other" option for custom responses.

```python
from edsl import QuestionMultipleChoiceWithOther

q = QuestionMultipleChoiceWithOther(
    question_name="source",
    question_text="How did you hear about us?",
    question_options=["Google", "Friend", "Advertisement"],
    other_option_text="Other"
)
```

`other_option_text` (default `"Other"`) is both the option label and the prefix a
write-in is matched against, so the answer comes back as `"Other: <text>"` when the
respondent supplies their own.

### QuestionCheckBoxWithOther

Checkbox with an "Other" option for custom responses.

```python
from edsl import QuestionCheckBoxWithOther

q = QuestionCheckBoxWithOther(
    question_name="channels",
    question_text="Which channels have you used to contact support? (Select all that apply)",
    question_options=["Email", "Phone", "Live chat"],
    min_selections=1,
    other_option_text="Other"
)
```

Write-ins arrive as ordinary members of the answer list, prefixed with
`other_option_text`. Unlike `QuestionMultipleChoiceWithOther`, a single answer can
carry several of them alongside predefined options:

```python
["Email", "Other: Community forum", "Other: In-app widget"]
```

`min_selections` / `max_selections` count write-ins the same as predefined options —
the answer above is three selections, so a `max_selections=2` would reject it.

### QuestionTopK

Select top K items from a list.

```python
from edsl import QuestionTopK

q = QuestionTopK(
    question_name="favorites",
    question_text="Select your top 3 favorite items:",
    question_options=["A", "B", "C", "D", "E"],
    k=3
)
```

### QuestionFileUpload

File upload for human respondents (`humanize` only). Respondents can upload one or more files.

Do not confuse this with attaching a researcher-provided stimulus through a
`FileStore`. `QuestionFileUpload` collects a new file from each respondent;
`FileStore` supplies a file to respondents or models as study input. It is not
a simulated-agent response type and should not be run as an ordinary LLM
question.

```python
from edsl import QuestionFileUpload, Survey

q = QuestionFileUpload(
    question_name="resume",
    question_text="Please upload your resume.",
)
```

### QuestionInterview

`QuestionInterview` supports two deployment modes:

1. **Human respondents** — deploy via `.humanize()`. See **ep-agent:methods-ai-interview** and **edsl:edsl-human-survey**.
2. **Simulated respondents** — run with `.by(agents).by(models).run()`. See **ep-agent:methods-ai-interview**.

**Humanize example:**

```python
from edsl import QuestionInterview, Survey

q = QuestionInterview(
    question_name="user_experience",
    question_text="We want to understand how you experience AI research tools in your daily work.",
    interview_guide=(
        "Thank you for taking part. Please share your thoughts on the following topics:\n\n"
        "1. How you currently use AI tools — walk us through a recent example.\n"
        "2. What frustrates you or doesn't work the way you'd expect.\n"
        "3. What you wish these tools could do that they can't yet.\n\n"
        "Write as much as feels natural. There are no right or wrong answers."
    ),
)

info = Survey([q]).humanize(human_survey_name="AI Tools Feedback")
print(info["respondent_url"])  # share with respondents
```

### QuestionFunctional

Python function-based question (not sent to LLM - computed locally).

```python
from edsl import QuestionFunctional

def compute_sum(scenario, agent):
    numbers = scenario.get("numbers", [])
    return sum(numbers)

q = QuestionFunctional(
    question_name="total",
    question_text="Calculate the sum",
    func=compute_sum
)
```

### QuestionPydantic

Use custom Pydantic models as response schemas.

```python
from edsl import QuestionPydantic
from pydantic import BaseModel

class PersonInfo(BaseModel):
    name: str
    age: int
    occupation: str

q = QuestionPydantic(
    question_name="person",
    question_text="Describe a person:",
    pydantic_model=PersonInfo
)
```

### QuestionMarkdown

Responses with markdown formatting.

```python
from edsl import QuestionMarkdown

q = QuestionMarkdown(
    question_name="formatted_response",
    question_text="Write a formatted response with headers and lists."
)
```

---

## Randomizing Answer-Option Order

Pass `questions_to_randomize` to the `Survey` constructor to shuffle the order of
answer options per respondent (controls for position bias). This works for **any
question type that has options** — multiple choice, checkbox, rank, top-k, etc. —
not just multiple choice. `questions_to_randomize` takes `question_name` values,
not variable names.

```python
from edsl import QuestionMultipleChoice, QuestionCheckBox, QuestionRank, Survey

q_brand = QuestionMultipleChoice(
    question_name="brand_preference",
    question_text="Which brand do you prefer?",
    question_options=["Nike", "Adidas", "Puma", "Reebok", "New Balance"]
)

# Randomize option order per respondent
survey = Survey(
    questions=[q_brand],
    questions_to_randomize=["brand_preference"]
)
```

Multiple questions of different types can be randomized in the same survey:

```python
q1 = QuestionMultipleChoice(
    question_name="q1",
    question_text="Which do you prefer?",
    question_options=["A", "B", "C"]
)
q2 = QuestionCheckBox(
    question_name="q2",
    question_text="Which do you like? (Select all that apply)",
    question_options=["X", "Y", "Z"]
)
q3 = QuestionRank(
    question_name="q3",
    question_text="Rank these in order of preference:",
    question_options=["P", "Q", "R"],
    num_selections=3
)
survey = Survey(
    questions=[q1, q2, q3],
    questions_to_randomize=["q1", "q3"]  # Only q1 and q3 randomized; q2 is not
)
```

To hold particular options in their original positions while shuffling the rest,
pass `options_to_pin={"brand_preference": ["Other"]}` alongside
`questions_to_randomize=["brand_preference"]` on a survey whose options include
`"Other"`. Pinning does not move an option to the end; put it there initially.
The locked EDSL revision preserves pins through Runner execution and JSONL
round trips. Inspect each result's recorded `question_options` when interpreting
coded answers. This randomizes answer options, not question order within blocks.

Whole option lists may also come from a scenario or a prior answer. EDSL resolves
the list before shuffling and reuses that interview's order for rendering,
validation, and result metadata. Configure this policy from the CLI with
`ep surveys set-option-randomization survey.ep --question brand_preference`
(add `--pin-options '{"brand_preference":["Other"]}'` to keep a value in its
source position); inspect settings with `ep surveys show survey.ep` and realized
orders with `ep results select --file results.ep --column
question_options.brand_preference`.

Do **not** randomize options that have an inherent order (Likert scales, numeric
ranges, yes/no).

---

## Jinja2 Templating Examples

### Scenario Templating

```python
from edsl import QuestionFreeText, Scenario

q = QuestionFreeText(
    question_name="opinion",
    question_text="What do you think about {{ scenario.fruit }}?"
)

scenarios = [
    Scenario({"fruit": "apples"}),
    Scenario({"fruit": "oranges"}),
]

results = q.by(scenarios).run(
    remote_inference_description="Fruit opinion survey",
    results_description="Fruit opinion survey",
)
```

### Agent Templating

```python
from edsl import QuestionFreeText, Agent

q = QuestionFreeText(
    question_name="perspective",
    question_text="As a {{ agent.occupation }}, what do you think about remote work?"
)

agent = Agent(traits={"occupation": "software engineer", "age": 35})
results = q.by(agent).run(
    remote_inference_description="Remote work perspectives by occupation",
    results_description="Remote work perspectives by occupation",
)
```

### Piping (Answer References)

Reference previous answers within a survey. **Important:** The answering LLM has no memory of prior questions — it only sees the resolved text. When a piped answer would be ambiguous on its own (a scale value, an option label, a short phrase), restate the original question and options so the follow-up is interpretable.

```python
q1 = QuestionMultipleChoice(
    question_name="preference",
    question_text="Which product do you prefer?",
    question_options=["Widget A", "Widget B", "Widget C"]
)
# Good: restates what was asked so the LLM has full context
q2 = QuestionFreeText(
    question_name="reason",
    question_text="You were previously asked 'Which product do you prefer: "
    "Widget A, Widget B, or Widget C?' and you said '{{ preference.answer }}'. "
    "Why did you make that choice?"
)
survey = Survey([q1, q2])
```

When the piped answer is self-explanatory in context, restating the original question is not necessary:

```python
q1 = QuestionFreeText(
    question_name="name",
    question_text="What is your name?"
)
q2 = QuestionFreeText(
    question_name="greeting",
    question_text="Hello {{ name.answer }}! How are you today?"
)
survey = Survey([q1, q2])
```

### Templating in Question Options

```python
q = QuestionMultipleChoice(
    question_name="preference",
    question_text="Which {{ scenario.category }} do you prefer?",
    question_options=[
        "{{ scenario.option_a }}",
        "{{ scenario.option_b }}",
        "{{ scenario.option_c }}"
    ]
)
```

### Using Prior Answers as Question Options

You can use a prior question's answer as the options for a follow-up question. This is especially useful with checkbox questions where you want to ask follow-ups about only the items the respondent selected.

#### Checkbox selections → Multiple choice options

```python
q1 = QuestionCheckBox(
    question_name="features",
    question_text="Which features do you like? (Select all that apply)",
    question_options=["Feature A", "Feature B", "Feature C", "Feature D"]
)

# Use the selected features as options in a follow-up
q2 = QuestionMultipleChoice(
    question_name="favorite",
    question_text="Which is your favorite among the features you selected?",
    question_options="{{ features.answer }}"
)

survey = Survey([q1, q2])
```

**Important:** The checkbox answer is a list of selected options. When used as `question_options` in a follow-up, it automatically becomes that question's option list.

#### Mixed fixed and piped options

A mixed literal/template list is supported for scalar additions, e.g.
`question_options=["Keep current", "{{ favorite.answer }}"]`, including an
`Other: ...` write-in. A whole list-valued answer still belongs in a whole
template string; a nested list is not the same option contract.

#### Checkbox selections → Matrix rows

```python
q1 = QuestionCheckBox(
    question_name="products",
    question_text="Which products have you used? (Select all that apply)",
    question_options=["Product A", "Product B", "Product C", "Product D", "Product E"]
)

# Rate only the products they've used
q2 = QuestionMatrix(
    question_name="ratings",
    question_text="Rate each product you've used:",
    question_items="{{ products.answer }}",  # Selected products become rows
    question_options=["Poor", "Fair", "Good", "Excellent"]
)

survey = Survey([q1, q2])
```

#### Checkbox selections → Rank question

```python
q1 = QuestionCheckBox(
    question_name="priorities",
    question_text="Which of these are priorities for you? (Select all that apply)",
    question_options=["Speed", "Cost", "Quality", "Support", "Innovation"],
    min_selections=2,
    max_selections=5
)

# Rank only the priorities they selected
q2 = QuestionRank(
    question_name="priority_ranking",
    question_text="Rank your selected priorities (1 = most important):",
    question_options="{{ priorities.answer }}"
    # num_selections omitted — defaults to ranking all provided options
)

survey = Survey([q1, q2])
```

**Note:** `num_selections` must be an integer at construction time (Jinja2 templates are not supported for this parameter). When the option count varies by respondent, omit `num_selections` entirely — the question will default to ranking all provided options.

---

## Looping Follow-Ups Over a List Answer

The patterns above ask **one** question about all the items at once. `Survey.loop_over()` asks a **block of questions once per item** — where the item list is itself an answer, not known until the run happens.

```python
Survey.loop_over(question, ask, item="item", max_items=None) -> Survey
```

| Argument | Meaning |
|----------|---------|
| `question` | The question (or its `question_name`) whose answer is the loop set. Should return a list — `QuestionList` or `QuestionCheckBox`. Must already be in the survey. |
| `ask` | A question, or list of questions, asked once per item. Must **not** already be in the survey. |
| `item` | Template key for the current item. Default `"item"`, so templates use `{{ item }}`. |
| `max_items` | Upper bound on iterations to materialize. Defaults to `Survey.DEFAULT_LOOP_MAX_ITEMS` (10). |

Returns `self`, so it chains. Like `add_question` and the other builder methods, it **mutates the survey in place** — if you need to keep an unexpanded copy, call `.duplicate()` first:

```python
looped = base.duplicate().loop_over("depts", ask=q_head, max_items=3)   # base unchanged
```

### Basic example

```python
from edsl import Survey, QuestionList, QuestionFreeText

q_depts = QuestionList(
    question_name="depts",
    question_text="List the departments you have worked in."
)

q_head = QuestionFreeText(
    question_name="head",
    question_text="Who heads {{ item }}, and how would you describe their leadership?"
)

survey = Survey([q_depts]).loop_over("depts", ask=q_head, max_items=3)

survey.question_names
# ['depts', 'head__loop0__depts', 'head__loop1__depts', 'head__loop2__depts']

survey.question_names_to_questions()["head__loop1__depts"].question_text
# 'Who heads {{ depts.answer[1] }}, and how would you describe their leadership?'
```

### How it works — static expansion

This is the key mental model. `loop_over` is **not** runtime machinery. At build time it expands into `max_items` plain copies of each `ask` question:

- `{{ item }}` is rewritten to `{{ <source>.answer[i] }}`, so the i-th item is **piped** in at render time.
- Each copy gets an auto-generated overflow guard skip rule — `{{ depts.answer }}[2:] == []` on iteration 2 — so iterations past the actual answer length are skipped and make **no model call**.
- `skip_when` / `jump_when` on the `ask` questions become native survey skip/jump rules on each copy.

The result is an ordinary survey with more questions. It runs identically on local, remote, and distributed runners, round-trips through `to_dict`/`from_dict`, and works in `humanize()` deployments (piping and skip rules are both supported there).

### Naming scheme and results columns

Expanded questions are named `<base>__loop<i>__<source>` (0-indexed), so results columns are stable: `answer.head__loop0__depts`, `answer.head__loop1__depts`, and so on.

Helpers for downstream analysis:

```python
Survey.parse_loop_question_name("head__loop2__depts")
# {'base': 'head', 'source': 'depts', 'index': 2}

Survey.parse_loop_question_name("risk_tolerance")   # not a loop question
# None

survey.loop_question_groups()
# {'depts': {'bases': ['head'],
#            'iterations': [['head__loop0__depts'],
#                           ['head__loop1__depts'],
#                           ['head__loop2__depts']],
#            'item_count': 3}}
```

**Unreached iterations are `None`, not missing.** A respondent who names 2 departments still produces a `head__loop2__depts` column, valued `None`. Filter it in analysis:

```python
answers = [a for a in results.select("head__loop0__depts",
                                     "head__loop1__depts",
                                     "head__loop2__depts").to_list()[0]
           if a is not None]
```

### Multi-question blocks with per-iteration logic

Attach conditional logic to the **template** question, not the survey. `skip_when(expression)` skips that question for iterations where the expression is truthy; `jump_when(expression, to=...)` jumps forward within the block.

```python
from edsl import Survey, QuestionList, QuestionFreeText, QuestionMultipleChoice, QuestionNumerical

q_risk = QuestionMultipleChoice(
    question_name="risk_tolerance",
    question_text="How would you describe your risk tolerance?",
    question_options=["low", "medium", "high"]
)

q_sectors = QuestionList(
    question_name="sectors",
    question_text="Which market sectors do you follow?"
)

# Asked once per sector
outlook = QuestionMultipleChoice(
    question_name="outlook",
    question_text="What is your outlook on {{ sector }}?",
    question_options=["bullish", "neutral", "bearish"]
).jump_when(
    "{{ outlook.answer }} == 'bearish'",
    to=QuestionMultipleChoice.NEXT_ITEM      # skip the rest of this item's block
)

concern = QuestionFreeText(
    question_name="concern",
    question_text="What is your biggest concern about {{ sector }}?"
).skip_when(
    "{{ outlook.answer }} == 'bullish' or {{ risk_tolerance.answer }} == 'high'"
)

allocation = QuestionNumerical(
    question_name="allocation",
    question_text="What percent of a portfolio would you allocate to {{ sector }}?"
)

survey = Survey([q_risk, q_sectors]).loop_over(
    "sectors",
    ask=[outlook, concern, allocation],
    item="sector",          # templates use {{ sector }} instead of {{ item }}
    max_items=3
)
```

**What expressions may reference:**

| Reference | Syntax | Note |
|-----------|--------|------|
| Earlier question in the same block | `{{ outlook.answer }}` | Use the **base** name; rewritten to the mangled name per iteration |
| Outer survey answer | `{{ risk_tolerance.answer }}` | Real name, passes through unchanged |
| Current item | `{{ scenario.sector }}` or `{{ sector }}` | Both work |
| Current index | `{{ scenario.loop_index }}` | Folded to an integer literal per iteration |

**Jump targets:** `QuestionBase.NEXT_ITEM` (value `"next_item"`, inherited by every question class, so `QuestionFreeText.NEXT_ITEM` works), or the `question_name` of a **later** question in the same block. Backward jumps and jumps out of the block are not supported. `END_OF_LOOP` is a deprecated alias for `NEXT_ITEM`.

### Constraints and gotchas

- **`max_items` is a hard ceiling.** Items beyond it are never asked and are silently lost. Set it from the source question's `max_list_items`, or cap the source: `QuestionList(..., max_list_items=3)` paired with `max_items=3`.
- **Only `question_text` and `question_options` are rewritten.** `{{ item }}` in `question_presentation`, `answering_instructions`, or matrix `question_items` is **not** substituted.
- **`ask` questions must not already be in the survey.** This is not enforced — passing a member question silently yields both the unlooped original and the copies.
- **The source is not type-checked.** A `QuestionFreeText` source is accepted, and `.answer[i]` will then index into a *string*, producing single characters.
- **Cost estimates count all `max_items` copies**, so a `max_items=10` block looks 10x more expensive than a realistic run. Correcting this needs `branch_weights` hung off the **last question of the block**, targeting the **first question after the loop block** (`EndOfSurvey` only when the block is last). Get either end wrong and the estimate silently understates: targeting `EndOfSurvey` while trailing questions exist strips reach from all of them, and anchoring on the block's *first* question drops the rest of the final item's questions. See `edsl:edsl-surveys-cost` for the survival-probability formula.
- **`NEXT_ITEM` on the final iteration jumps to `EndOfSurvey`**, so any non-loop questions placed after the block get skipped when the last item fires that jump. Add the loop block last, or use an explicit in-block jump target.
- **Template questions carrying loop rules do not round-trip alone.** `QuestionBase.from_dict(q.to_dict())` on a question with `skip_when`/`jump_when` raises `QuestionInitializationError`. The expanded *survey* serializes fine.
- **Avoid nested loops.** Looping over a materialized copy (`loop_over("people__loop0__depts", ...)`) works mechanically but requires one call per outer iteration and multiplies question count combinatorially. Restructure instead.

### `loop_over` vs `Question.loop()`

Two different tools, easy to confuse:

| | `Question.loop(scenario_list)` | `Survey.loop_over(question, ask=...)` |
|---|---|---|
| Loop set known | **Before** the run (a `ScenarioList`) | **At run time** — another question's answer |
| Returns | `List[QuestionBase]` — pass to `Survey(...)` | `Survey` (self, mutated) |
| Values | Baked into text at construction | Piped at render time |
| Bounded? | Exact, unbounded | Must be bounded by `max_items` |
| Naming | Placeholder substituted, e.g. `head_Engineering` | `<base>__loop<i>__<source>` |

Use `Question.loop()` when *you* know the list (product names, sectors, transcript segments). Use `Survey.loop_over()` when the **respondent** supplies the list. Note that `scenario_list_method="loop"` in `humanize()` is a third, unrelated thing — it repeats the whole survey for every scenario.

---

## Survey Rules Examples

### Skip Rules (Before Rules)

```python
survey = survey.add_skip_rule(
    "pet_name",
    "{{ has_pet.answer }} == 'No'"
)
```

### Navigation Rules (After Rules)

```python
survey = (survey
    .add_rule("preference", "{{ preference.answer }} == 'A'", "section_a")
    .add_rule("preference", "{{ preference.answer }} == 'B'", "section_b"))
```

### Stop Rules (Early Termination)

```python
survey = survey.add_stop_rule(
    "eligibility",
    "{{ eligibility.answer }} == 'No'"
)
```

### EndOfSurvey Marker

```python
from edsl.surveys import EndOfSurvey

survey = survey.add_rule("screening", "{{ screening.answer }} == 'disqualified'", EndOfSurvey)
```

### Expression Syntax

```python
"{{ question_name.answer }} == 'value'"
"{{ age.answer }} > 18"
"{{ q1.answer }} == 'yes' and {{ q2.answer }} != 'no'"
```

---

## Survey Memory Decision Guide

Work through these steps before adding any memory rule:

> **HUMANIZE:** If the survey will be deployed via `.humanize()`, skip memory APIs entirely — they do not apply. Use piping (`{{ q_name.answer }}`) for any cross-question context. See **edsl:edsl-human-survey** — "Memory and piping".

**Step 1: Can you use piping instead?**

Piping is always the first choice. If a later question needs to reference a prior answer, embed it directly in the `question_text`. This is explicit, zero-cost, and does not introduce hidden carry-over effects on other questions:

```python
QuestionFreeText(
    question_name="q2",
    question_text=(
        "In a previous question you were asked: {{ q1.question_text }}; "
        "you answered: {{ q1.answer }}. Now please explain your reasoning."
    )
)
```

Use piping whenever one or two specific prior answers are needed. This is the preferred approach.

**Step 2: Are the questions truly independent?**

If questions measure separate constructs and do not reference each other, use **no memory (the default)**. Adding memory to independent questions introduces carry-over bias — agents anchor later answers to earlier ones even when that is not warranted. It also increases token cost on every question after the first.

**Step 3: Does the survey simulate a genuine back-and-forth conversation?**

Full memory is appropriate only when the survey is structured as an interview or dialogue where each question genuinely builds on the entire prior exchange — for example, a multi-turn follow-up interview where the agent's role is to respond coherently to a developing conversation. Even then, consider whether targeted memory on specific questions would be cleaner.

### Cost and bias warnings

**Do not apply `set_full_memory_mode()` as a default or "safe" setting.** It is not safe — it has real costs:

- **Token cost**: Q12 in a 12-question survey is sent with 11 prior Q&A pairs injected into its context. This multiplies cost roughly proportionally to survey length.
- **Carry-over bias**: Agents anchor later answers to earlier ones. For surveys measuring independent constructs this is a confound, not a feature.
- **Order effects**: The sequence of questions becomes an experimental variable you did not intend to introduce.

## Survey Helper Utilities

### Matrix Combiner

```python
from edsl.surveys.survey_helpers.matrix_combiner import combine_multiple_choice_to_matrix

new_survey = combine_multiple_choice_to_matrix(
    survey=survey,
    question_names=["trust_freelancer", "trust_ai", "trust_agency"],
    matrix_question_name="trust_matrix"
)
```

---

## run() Parameters

Pass `remote_inference_description` and `results_description` to `.run()` to label the job in the Expected Parrot remote inference queue and saved Results object. Both accept a plain string; matching values make the artifacts easier to associate.

```python
results = survey.by(scenario_list).by(agent_list).by(model_list).run(
    remote_inference_description="Policy support — UBI carbon tax tuition — 150 agents",
    results_description="Policy support — UBI carbon tax tuition — 150 agents",
)
```

Descriptive labels can include the study name and run type to make jobs and results easier to identify.

---

## Retrieving error reports for failed jobs

If a remote job fails, retrieve a markdown-formatted exception report using the job's UUID to help with debugging:

```bash
ep jobs errors <job-uuid> --output error_report.md
```
