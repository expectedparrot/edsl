## Humanize schema — styling and question configuration

## Contents

- [Making questions optional](#making-questions-optional)
- [Format options by question type](#format-options-by-question-type)
- [Matrix preselection](#matrix-preselection)
- [Survey progress](#survey-progress)
- [Requiring Expected Parrot login](#requiring-expected-parrot-login)
- [Survey logo](#survey-logo)
- [Question time limits](#question-time-limits)
- [Attention checks (custom validation)](#attention-checks-custom-validation)
- [Exclusive options (checkbox)](#exclusive-options-checkbox)
- [Distribution questions](#distribution-questions)
- [Submitting indicator](#submitting-indicator)
- [Full schema support matrix](#full-schema-support-matrix)
- [Reading a deployed schema](#reading-a-deployed-schema)
- [Checkbox Select all](#checkbox-select-all)
- [Updating the schema on a live survey](#updating-the-schema-on-a-live-survey)

The `humanize_schema` parameter controls how questions render in the web UI. It is a dict with two optional top-level keys:

```python
humanize_schema = {
    "questions": {
        "question_name": { ... },  # per-question config
    },
    "survey": {
        "custom_css": "...",       # survey-wide CSS
        "login_required": True,    # require an Expected Parrot account
        "progress": {"type": "bar"},
        "branding": {"logo": {...}},
    }
}
```

### Requiring Expected Parrot login

Set `survey.login_required` to `True` to require browser respondents to sign in
to an Expected Parrot account. Logged-out visitors are sent to sign in and
returned to the survey afterward. The same option is available in the survey's
owner settings under **Survey settings → Account required**.

```python
schema = {"survey": {"login_required": True}}
info = survey.humanize(human_survey_name="Study", humanize_schema=schema)
```

For a deployed survey, save the partial schema as `schema-patch.json` and patch it
without creating a new survey link:

```json
{"survey": {"login_required": true}}
```

```bash
ep humanize schema patch <human-survey-uuid> --schema schema-patch.json
```

When enabled, completed responses include the respondent's account username as
the `agent.expectedparrot_username` result trait. This identifies respondents
by their Expected Parrot username; explain its collection and use to
participants.

Prolific participants must sign in too. A survey that requires sign-in can't be
taken by an AI agent through its agent link, even with agent access on. Its
preview links also need sign-in: any signed-in Expected Parrot account can open
them.

### Making questions optional

By default all questions are required. Set `optional: True` to let respondents skip:

```python
schema = {
    "questions": {
        "feedback": {"optional": True},
    }
}
info = survey.humanize(human_survey_name="Study", humanize_schema=schema)
```

### Format options by question type

Some question types support a `format` field to change the UI widget:

| Question type | Format options | Default |
|---|---|---|
| `multiple_choice` | `"radio"`, `"dropdown"` | `"radio"` |
| `likert_five` | `"radio"`, `"dropdown"` | `"radio"` |
| `linear_scale` | `"radio"`, `"dropdown"` | `"radio"` |
| `yes_no` | `"radio"`, `"dropdown"` | `"radio"` |
| `numerical` | `"input"`, `"slider"` | `"input"` |

```python
schema = {
    "questions": {
        "rating": {
            "format": {"type": "slider", "min": 0, "max": 100, "step": 5}
        },
        "category": {
            "format": {"type": "dropdown"}
        },
    }
}
```

Slider format (numerical only) supports `min`, `max`, and `step` (all floats, validated: min < max, step > 0).

For a matrix, `format` controls whether respondents see the full grid or one
row at a time:

```python
schema = {
    "questions": {
        "ratings": {
            "format": {"type": "carousel", "advance_on_select": True}
        }
    }
}
```

Use `{"type": "table"}` for the whole grid (default). Use carousel for long
column labels or phone-heavy samples. `advance_on_select` defaults to `True`;
set it to `False` when respondents are likely to review and revise answers.

### Matrix preselection

Preselection fills a matrix column before the respondent arrives:

```python
schema = {
    "questions": {
        "ratings": {
            "preselection": {
                "rules": [{
                    "match": {"type": "all"},
                    "option": {"type": "text", "value": "Neutral"},
                }]
            }
        }
    }
}
```

The preselected option text must exactly match one of `question_options`. A preselected value is present before the respondent interacts with the question.

### Survey progress

Surveys show a percent-labelled bar by default. Configure it under `survey`:

```python
{"survey": {"progress": {"type": "bar", "label": {"type": "percent"}}}}
```

Use `{"type": "hidden"}` for no indicator. Use `{"type": "steps",
"marker": "number", "steps": [...]}` for named or numbered sections; every
non-final step needs a `complete_after` question/instruction name, while the
final step may omit it. Ask whether the researcher wants the default bar,
hidden progress, or meaningful steps when survey length or section structure
makes progress feedback consequential.

### Survey logo

`survey.branding.logo` draws a logo in a banner above the questions. A schema
never carries image bytes: upload the image to the asset library first and
reference its uuid.

```bash
ep humanize schema set <human-survey-uuid> --logo-file lab_logo.png --logo-alt "Acme Research logo" --logo-position center
```

`alt` is required (up to 200 characters); use `""` to mark the logo decorative.
`position` is `"left"` (default), `"center"`, or `"right"`. There is no size
field; resize with `.edsl-logo` in `custom_css` (see **edsl:edsl-human-survey-css**).
Uploads accept PNG, JPEG, WebP, and static GIF up to 2 MB and 4096 px per side.
Re-uploading an identical file returns the existing asset.

From the CLI:

```bash
ep humanize assets upload lab_logo.png
ep humanize assets list
ep humanize schema set <uuid> --logo-asset <asset_uuid> --logo-alt "Acme Research logo"
ep humanize schema set <uuid> --logo-file lab_logo.png --logo-alt "Acme Research logo"
ep humanize schema set <uuid> --clear-logo
```

`--logo-file` uploads and applies in one step and works only on `schema set`;
`schema create` makes no server calls, so it takes `--logo-asset`. A new logo
needs `--logo-alt` or `--logo-decorative`. `--logo-alt`, `--logo-decorative`, or
`--logo-position` alone patches that field of the existing logo.

When a schema names another author's asset, it is copied into your library and
the uuid rewritten; the create response reports the mapping in
`asset_substitutions`.

### Question time limits

`time_limit` shows a countdown above the question. At zero the answer locks and
the respondent clicks **Next**; whatever they entered is submitted, and an
unanswered question is recorded as unanswered even if it is not optional.

```python
schema = {
    "questions": {
        "feedback": {"time_limit": {"duration": {"type": "fixed", "seconds": 300}}},
    }
}
```

`seconds` must be 30–7200, and `"type": "fixed"` is required. Time limits are
ignored under `survey.presentation: "group"`, even for a question alone in its
group. The countdown runs in the browser, so a reload restarts it. A time limit
changes what is measured; confirm it with the researcher and record it in the
plan.

### Attention checks (custom validation)

Multiple choice questions support `custom_validation` to require a specific answer — useful for attention checks:

```python
schema = {
    "questions": {
        "attention_check": {
            "custom_validation": {"select_exact_answer": "Blue"}
        }
    }
}
```

### Exclusive options (checkbox)

`checkbox` and `checkbox_with_other` support `exclusive_options` — options that stand alone. Checking one clears every other selection; selecting anything else clears it.

```python
schema = {
    "questions": {
        "channels": {
            "exclusive_options": ["None of the above"],
        }
    }
}
```

Each entry must match an option in the question's `question_options` **exactly**, byte for byte — this marks a "None of the above" you already wrote rather than injecting a new label, so the submitted answer stays an ordinary member of the option list. Entries are not whitespace-stripped, and duplicates are rejected. More than one option can be exclusive; checking either clears the other. On `checkbox_with_other`, an exclusive option also clears the respondent's write-in entries.

Omit the key for the default: no option is exclusive.

### Distribution questions

Respondents answer a `QuestionDistribution` by painting probability across its
outcomes or bins; the percentages always total 100%. Two settings apply:

```python
schema = {
    "questions": {
        "commute_minutes": {
            "initial_distribution": {"type": "empty"},
            "distribution_summary": {"statistics": [{"type": "mean"}]},
        }
    }
}
```

`initial_distribution` is `{"type": "uniform"}` (default) or `{"type": "empty"}`.
Uniform gives every bin equal probability regardless of width, and a respondent
can submit it untouched, so an untouched answer is indistinguishable from an
endorsed uniform belief. Empty requires painting before **Next**. This anchors
responses like matrix preselection: confirm the choice with the researcher.

`distribution_summary` shows implied statistics beneath the chart, updated as
the respondent paints; omit it for none. `statistics` lists `{"type": "mean"}`
and/or `{"type": "variance"}` in display order (default: both). They assume
probability is spread evenly within each bin, appear only for finite numeric
bins, and do not change the submitted answer.

Distribution questions accept no other per-question keys: they cannot be
`optional` and take no `time_limit` or `submitting_indicator`.

### Submitting indicator

**Only set this when a background question runs immediately after the question** — a thinking question or a `QuestionImageGeneration`. That inference is the wait it covers; on an ordinary question the next screen appears at once, and the callout flashes up for no reason.

When a respondent clicks **Next** and a background question runs in between, `submitting_indicator` shows a callout box during that wait instead of leaving the respondent on an unresponsive screen. Match the title to what is actually happening — "Analyzing your answer…" for a classification step, "Creating your image…" for a generation, which is a wait long enough that an unlabeled screen reads as broken:

```python
schema = {
    "questions": {
        "issue_description": {
            "submitting_indicator": {"type": "callout", "title": "Analyzing your answer…"},
        }
    }
}
```

Set it on the question the respondent submits, not the background question that runs afterward. `type` must be `"callout"`. `title` is optional (1–200 characters); omit it to get the default, "Processing your response...". The callout always carries the subtitle "We'll continue automatically when it's ready."

Supported on every question type except `compute` and `image_generation` (both auto-advance, so they are never submitted), `interview`, and `distribution`. For those, set the indicator on the visible question that precedes them.

### Full schema support matrix

| Question type | `optional` | `format` | `custom_validation` |
|---|---|---|---|
| `free_text` | yes | — | — |
| `budget` | yes | — | — |
| `checkbox` | yes | — | — |
| `checkbox_with_other` | yes | — | — |
| `demand` | no | — | — |
| `dict` | no | — | — |
| `distribution` | no | — | — |
| `dropdown` | yes | searchable option picker | — |
| `edit` | yes | — | — |
| `email` | yes | — | — |
| `file_upload` | yes | — | — |
| `interview` | yes | — | — |
| `likert_five` | yes | radio/dropdown | — |
| `linear_scale` | yes | radio/dropdown | — |
| `list` | yes | — | — |
| `matrix` | yes | table/carousel | — |
| `multiple_choice` | yes | radio/dropdown | `select_exact_answer` |
| `multiple_choice_with_other` | yes | — | — |
| `numerical` | yes | input/slider | — |
| `rank` | yes | — | — |
| `top_k` | yes | — | — |
| `url` | yes | — | — |
| `yes_no` | yes | radio/dropdown | — |

`time_limit` is accepted by every type in the table except `interview` and `distribution`.

`dropdown` uses the question's large option set. Respondents enter search terms in a combo box, choose from up to `top_k` ranked matches (5 by default), and the chosen option fills the input. The stored EDSL answer remains a one-item list holding the option's text. Respondents must choose a listed option.

`javascript` (custom JavaScript hooks) is accepted by every question type except `compute` and `image_generation`, on approved accounts only — see `edsl:edsl-human-survey-javascript`.

`submitting_indicator` is accepted by every question type except `interview`, `distribution`, `compute`, and `image_generation` (the last two auto-advance, so they are never submitted) — see "Submitting indicator" above for when to set it.

`interview` also supports `interview_mode`: text (default), voice, or both. It also supports `intro_screen` (custom text shown before the interview starts, both modes), `voice_interview_config` (spoken language and `voice_option` for how the AI interviewer sounds in voice mode), and `text_interview_config` (language, interviewer name, end message, checklist, end policy, composer locking). A text interviewer can also show images inline from an attached scenario. See "Using QuestionInterview with humanize" below.

### Reading a deployed schema

```bash
ep humanize schema get <uuid> --out schema.json
```

Without `--out`, the JSON envelope contains `data.humanize_schema`. Python users
can call `Coop().get_human_survey_humanize_schema(uuid)`; it returns the stored
schema or `None` if none was set. `.json.gz` output is compressed; other suffixes
produce plain JSON. Inspect current settings before constructing a narrow patch,
especially when replacing lists such as checklist items.

### Checkbox Select all

Set `{"questions": {"features": {"select_all": None}}}` in Python (JSON `null`)
to remove the ordinary checkbox Select all control. Omitting the field preserves
the default. It does not apply to `checkbox_with_other`, which has no such control.
Exclusive options are excluded from Select all. The only accepted label is
`"Select all"`; this is not a way to customize its wording.

### Updating the schema on a live survey

To change the humanize schema after a survey is already deployed — without re-running `.humanize()` and minting a new survey — patch it on Coop. This is the practical way to tweak `QuestionInterview` settings (checklist, end policy, interviewer name, mode) on a live interview.

```json
{"questions": {"my_interview": {"text_interview_config": {"interviewer_name": "Dr. Lopez"}}}}
```

```bash
ep humanize schema patch <human-survey-uuid> --schema schema-patch.json
```

The `partial_schema` is **deep-merged** into the stored schema: nested dicts merge key-by-key, so the call above changes only `interviewer_name` and leaves the rest of `text_interview_config` untouched. But lists, scalars, and explicit `None` **replace** the existing value wholesale — sending a `checklist` `items` list replaces the whole array rather than appending. The merged result is re-validated as a whole, so unknown keys or invalid values are rejected (`HumanizeSchemaValidationError`). Returns `{"humanize_schema": <updated schema>}`.
