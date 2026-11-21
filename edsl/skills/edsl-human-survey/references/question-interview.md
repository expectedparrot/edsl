## Using QuestionInterview with humanize

`QuestionInterview` is supported by humanize. Respondents get a chat interface for text mode or a voice call interface for voice mode. The `question_text` is not displayed to the respondent — it is used internally. The input mode is controlled via `humanize_schema`:

| `interview_mode` | Behavior |
|-----------------|----------|
| `"text"` (default) | Text-based interview |
| `"voice"` | Voice-based interview |
| `"both"` | Respondent chooses between text and voice |

**Mic dictation vs. voice mode — two different things, both inside the interview.** In a **text** interview the respondent can dictate their messages with an intercom-style mic button instead of typing: it transcribes speech into the composer (speech-to-text) and they can edit the text before sending. It is still a text interview — what gets stored is the written transcript. A **voice** interview (`interview_mode: "voice"`) is a different thing: a spoken call with the AI interviewer. Under `"both"` the respondent chooses, so whoever picks text gets dictation and whoever picks voice gets the call. Dictation belongs to the text interview only; the survey's other questions have no mic button. When a user talks about "voice," clarify which they mean — dictating into the text interview or an actual voice interview.

### Intro screen (`intro_screen`)

An intro screen is always shown before the interview starts. By default it displays generic text ("This will be a conversation with an AI agent."). Set `intro_screen` to supply your own body text — a chance to greet the respondent, set expectations, or give consent language. It applies to both text and voice modes (it's a top-level interview field, not inside `text_interview_config` / `voice_interview_config`).

When `interview_mode` is `"both"`, the intro screen is also where the respondent picks text or voice before continuing, so your `instruction` sits alongside that choice.

```python
schema = {
    "questions": {
        "my_interview": {
            "intro_screen": {
                "type": "default",
                "instruction": "You'll chat with an AI interviewer about your recent job search. There are no right answers — we're interested in your experience. This should take about 10 minutes.",
            },
        }
    }
}
```

| Field | Notes |
|---|---|
| `type` | Must be `"default"` (the only variant today). |
| `instruction` | Body text shown on the intro screen; 1–2500 chars. Omit `intro_screen` entirely to keep the generic default. |

Patch it on a live survey via `Coop().patch_human_survey_humanize_schema()` (see "Updating the schema on a live survey" above).

### Voice-mode configuration (`voice_interview_config`)

For voice-mode interviews (ignored when `interview_mode` is `"text"`), pass a `voice_interview_config` dict to set the spoken language and how the AI interviewer sounds during the voice call:

```python
schema = {
    "questions": {
        "my_interview": {
            "interview_mode": "voice",
            "voice_interview_config": {
                "language": "french",
                "voice_option": "coral",
            },
        }
    }
}
```

| Field | Notes |
|---|---|
| `language` | Lowercase language id. Default `"english"` when omitted or blank. `"multilingual"` auto-detects the respondent's spoken language. |
| `voice_option` | Which speaking voice the AI interviewer uses. Lowercase id from the list below. Omit to keep the deployment default (usually marin). Ignored for text mode; under `"both"`, it applies only when the respondent picks voice. |

When talking to the researcher, ask which **voice** or how the interviewer should **sound** — do not say `voice_option` or other schema field names. Offer the named options below if they want a choice; if they have no preference, omit the field.

Allowed `voice_option` ids: `alloy`, `ash`, `ballad`, `cedar`, `coral`, `echo`, `marin`, `sage`, `shimmer`, `verse`. Unknown ids are rejected.

GPT-Live only ids: `beacon`, `bossa`, `brise`, `cinder`, `delta`, `flitz`, `gleam`, `harema`, `juni`, `meridian`, `nira`, `noeul`, `nuri`, `quartz`, `ripple`, `shida`, `sillage`, `stone`, `tempo`, `vesper`, `willow`. These are spoken only in Voice only interviews, which run on GPT-Live; a Voice + live transcript interview uses the default voice instead. If the researcher picks one, tell them that in plain words.

Full supported language list and multilingual guidance → `references/interview-languages.md` (shared with text mode). If a **prior question** selects the interview language, fork one `QuestionInterview` per language and skip-route — do not try to Jinja the language field (see that reference).

Patch language or voice on a live survey via `Coop().patch_human_survey_humanize_schema()` (see "Updating the schema on a live survey" above).

### Voice turn-taking speed

Set `voice_interview_config.turn_taking.initial_speed` to `"fastest"`, `"faster"`,
`"default"`, `"slower"`, or `"slowest"`. For respondents who pause mid-thought:

```python
voice_interview_config = {
    "language": "english",
    "turn_taking": {"initial_speed": "slower"},
}
```

This changes the pause before the interviewer takes a turn, not synthesized
speech speed. Omission uses `"default"`; respondents can change the setting
during the call. It applies to voice mode, including voice selected in `"both"`.

### Text-mode configuration (`text_interview_config`)

For text-mode interviews (ignored when `interview_mode` is `"voice"`), pass a `text_interview_config` dict to set the interview language, customize the interviewer label, the closing message, an interviewer checklist, mid-interview structured questions, how the interview is allowed to end, and whether the participant can type while the interviewer is replying:

```python
schema = {
    "questions": {
        "my_interview": {
            "interview_mode": "text",
            "text_interview_config": {
                "language": "spanish",
                "interviewer_name": "Dr. Lopez",
                "end_interview_message": "Thanks — that's everything. Your responses are recorded.",
                "checklist": { ... },
                "structured_questions": { ... },
                "end_policy": { ... },
                "participant_chat_during_reply": "open",
            },
        }
    }
}
```

| Field | Notes |
|---|---|
| `language` | Lowercase language id for the written interview. Default `"english"` when omitted or blank. Same list as voice → `references/interview-languages.md`. |
| `interviewer_name` | Label shown above interviewer messages. 1–200 chars. Default `"AI Interviewer"`. |
| `end_interview_message` | Shown after the respondent presses the End Interview button. 1–2500 chars. Has a sensible default. |
| `checklist` | Items the interviewer works through. See below. |
| `structured_questions` | Lets the interviewer pose multiple-choice / numerical questions as input widgets mid-interview. See below. |
| — | Showing images mid-interview needs no schema field: attach them to a scenario and name the keys in the guide. See "Showing images mid-interview" below. |
| `end_policy` | Who controls when the interview can end. See below. |
| `participant_chat_during_reply` | Whether the participant can type while the interviewer's reply is generating. `"open"` (default) or `"locked"`. See below. |

#### Checklist

A checklist gives the interviewer a set of items to work through during the conversation. The model marks items off as their conditions are met; `participant_visibility` controls whether the respondent sees a floating checklist panel.

```python
"checklist": {
    "initial": {
        "type": "manual",
        "items": [
            {
                "id": "consent",
                "label": "Confirmed consent",
                "instructions": "Check off once the respondent has explicitly agreed to participate.",
            },
            {
                "id": "first_job",
                "label": "Described their first job",
                "instructions": "Check off once they have described a specific first job, not a general statement.",
            },
        ],
    },
    "participant_visibility": "visible",
}
```

| Field | Notes |
|---|---|
| `initial.type` | Must be `"manual"`. |
| `id` | Unique within the checklist; 1–64 chars; letters, digits, underscores, hyphens only. |
| `label` | Participant-facing text shown in the checklist UI; 1–200 chars. |
| `instructions` | Model-facing condition for checking the item off; 1–2000 chars. |
| `participant_visibility` | `"visible"` (default) shows the panel; `"hidden"` keeps it a pure interviewer instrument (status still tracked internally). |

#### Structured questions (text only)

By default a text interview is pure prose. Add `structured_questions` to let the interviewer surface **multiple-choice** and **numerical** questions mid-conversation as input widgets (radio buttons, a number field) instead of free typing — useful when you want clean, coded answers for specific points without breaking the conversational flow.

When `structured_questions` is enabled, the interviewer may present supported multiple-choice or numerical widgets according to the interview guide.

```python
# Allow both widget types (equivalent to omitting the list)
"structured_questions": {"allowed_types": ["multiple_choice", "numerical"]}

# Restrict to numerical widgets only
"structured_questions": {"allowed_types": ["numerical"]}
```

| Field | Notes |
|---|---|
| `allowed_types` | Which widget types the interviewer may use: `"multiple_choice"`, `"numerical"`, or both. Defaults to both when the key is omitted. Must be non-empty and free of duplicates — to disable structured questions entirely, omit `structured_questions` rather than passing an empty list. |

**Surfacing them from the interview guide.** Enabling `structured_questions` only grants the capability; the model decides when to use it based on your `interview_guide`. To make it reliable, write explicit instructions in the guide at each point you want a structured question:

- **Name the moment and the payload.** Say when the interviewer should ask and spell out the exact answer options (for multiple choice) or the accepted range (for numerical) — e.g. "ask which pricing plan they lean toward as a multiple-choice question with exactly three choices: 'Basic', 'Plus', 'Premium'" or "ask how many hours per week they spend cooking as a numerical question accepting a number from 0 to 40."
- **Tell it to render as a structured question, not prose.** The model will otherwise just type the question into its message. Add a directive like "Do not write the question into your message text; present it as a structured question."
- **Only reference enabled types.** If `allowed_types` is `["numerical"]`, don't instruct the guide to pose multiple-choice questions — the interviewer can't render them and will fall back to prose.

Keep the structured question confined to the coded answer; let surrounding rapport, probing, and transitions stay in ordinary conversational text.

#### Showing images mid-interview (text only)

A text interviewer can display images inline in the chat. Attach them as `FileStore` values on a scenario, then tell the guide which key to show and when. There is no `humanize_schema` field for this — the scenario keys and the guide are the whole mechanism.

```python
from edsl.scenarios import FileStore, Scenario, ScenarioList

# key -> image file; the keys are what the interview guide refers to
stimuli = {
    "package_a": "assets/package_a.png",
    "package_b": "assets/package_b.png",
}
scenarios = ScenarioList([Scenario({key: FileStore(path) for key, path in stimuli.items()})])

info = Survey([q_design_reactions]).by(scenarios).humanize(
    human_survey_name="Package design interviews",
    scenario_list_method="single_scenario",
    humanize_schema={"questions": {"design_reactions": {"interview_mode": "text"}}},
)
```

In the guide, name the keys and the moment:

```
Show package_a and ask what stands out to them. Once they have answered,
show package_b and ask which one they would pick up in a store. Show each
image once; do not show either again later in the conversation.
```

- **Text mode only.** Voice interviews cannot display anything. Under `"both"`, whoever picks voice never sees the images — if the images are essential, set `interview_mode` to `"text"` rather than leaving the choice open.
- **The keys are the contract.** A key named in the guide that isn't in the scenario renders nothing, and the interviewer will usually carry on as if it had shown. Keep the two lists in sync when either changes.
- **Say when *not* to show, too.** Every image in the scenario is available for the whole interview, so an unconstrained guide will re-show them. Spell out the trigger ("only when re-asking after a wrong answer") and the exclusions ("never in the opening message or the closing line").
- Use `single_scenario` when every respondent sees the same set, `randomize` to hand each respondent a different stimulus set. `.preview()` does not render scenarios — check the images with `info["preview_url"]`.

#### End policy

Controls who decides when the interview is over. Omit for the default (`{"control": "respondent"}`).

```python
# Default: participant can end at any time
"end_policy": {"control": "respondent"}

# Gated: End Interview button hidden until the model signals its goals are met
"end_policy": {
    "control": "interviewer_gated",
    "interview_marked_complete_message": {
        "message": "I have everything I need — thank you for your time.",
        "method": "replace",
    },
    "participant_chat_after_complete": "open",
}
```

| `control` | Behavior |
|---|---|
| `"respondent"` (default) | Participant can end at any time; End Interview button always available. No other fields apply. |
| `"interviewer_gated"` | End Interview button is hidden until the model marks its goals met. Pairs well with a checklist. Accepts `interview_marked_complete_message` and `participant_chat_after_complete`. |

`interview_marked_complete_message` (interviewer_gated only) surfaces a fixed message on the turn the interviewer first marks the interview complete. `message` is 1–2500 chars; with `method: "replace"`, that message is shown instead of model-generated text. Omit to let the model generate the turn.

`participant_chat_after_complete` (interviewer_gated only) controls what the participant can still do once the interviewer has marked the interview complete:

| Value | Behavior |
|---|---|
| `"open"` (default) | The composer stays live — the participant can keep talking after the mark; ending is optional. |
| `"locked"` | The composer closes with the mark, so the marking turn is the last thing the participant reads and ending is their only remaining action. |

Use `"locked"` when you want a clean, fixed stopping point — typically paired with `interview_marked_complete_message` so the final turn reads as a deliberate sign-off rather than a conversation that suddenly can't continue. Keep the default `"open"` when late additions from the respondent are still valuable.

#### Chat while the interviewer is replying

`participant_chat_during_reply` controls whether the composer stays usable during the seconds the interviewer's reply is being generated. Unlike `end_policy.participant_chat_after_complete`, this is a per-turn lock that reopens once the reply lands, and it applies under either end policy.

```python
"participant_chat_during_reply": "locked"
```

| Value | Behavior |
|---|---|
| `"open"` (default) | The composer stays live — the participant can type ahead of a reply they haven't read yet. |
| `"locked"` | The composer closes until the reply arrives, so every reply is read before anything is written against it. |

Leave this at `"open"`. Only set `"locked"` when the user explicitly asks for it — do not switch it on your own initiative or suggest it unprompted.

For the full workflow — `interview_guide.md` and `deploy_interview.py` in the job directory — see **ep-agent:research-interview-design**.
