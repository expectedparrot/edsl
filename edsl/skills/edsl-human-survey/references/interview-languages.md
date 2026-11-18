# Interview languages

Supported `language` ids for `QuestionInterview`, shared by both `voice_interview_config.language` (voice/`"both"` modes) and `text_interview_config.language` (text/`"both"` modes) — the same list validates both. Use the **id** in schema — not the display name.

| id | Display name |
|----|--------------|
| `english` | English |
| `french` | French |
| `german` | German |
| `spanish` | Spanish |
| `portuguese` | Portuguese |
| `chinese` | Chinese |
| `japanese` | Japanese |
| `hindi` | Hindi |
| `italian` | Italian |
| `korean` | Korean |
| `dutch` | Dutch |
| `polish` | Polish |
| `russian` | Russian |
| `swedish` | Swedish |
| `turkish` | Turkish |
| `tagalog` | Tagalog |
| `bulgarian` | Bulgarian |
| `romanian` | Romanian |
| `arabic` | Arabic |
| `czech` | Czech |
| `greek` | Greek |
| `finnish` | Finnish |
| `croatian` | Croatian |
| `malay` | Malay |
| `slovak` | Slovak |
| `danish` | Danish |
| `tamil` | Tamil |
| `ukrainian` | Ukrainian |
| `hungarian` | Hungarian |
| `norwegian` | Norwegian |
| `vietnamese` | Vietnamese |
| `bangla` | Bangla |
| `thai` | Thai |
| `hebrew` | Hebrew |
| `georgian` | Georgian |
| `indonesian` | Indonesian |
| `telugu` | Telugu |
| `gujarati` | Gujarati |
| `kannada` | Kannada |
| `malayalam` | Malayalam |
| `marathi` | Marathi |
| `punjabi` | Punjabi |
| `multilingual` | Multilingual — auto-detect respondent language |

## Multilingual mode

`multilingual` lets the interviewer detect and match the respondent's language — spoken during the call for voice mode, written for text mode. Prefer it when respondents may use different languages or you are unsure which single language to set. For a homogeneous audience, a specific language id is clearer for analysis and guide alignment.

This native `language`/`multilingual` config applies to `QuestionInterview` only. **Structured** questions have no built-in language setting, but their `question_text` supports Jinja `{% if %}`, so a question's wording can branch on a prior answer (a language choice being one option) — see **edsl:edsl-surveys** ("Jinja if/then for per-answer wording").

## Language chosen by a prior question → fork interviews + skip logic

`text_interview_config.language` / `voice_interview_config.language` are fixed per `QuestionInterview` in the humanize schema. They cannot branch on `{{ prior.answer }}`. If an earlier survey question records the interview language (or you infer it from an answer), do **not** rely on one interview with `multilingual` or try to Jinja the language field.

Instead:

1. Ask (or detect) the language in a prior question.
2. Create a **separate `QuestionInterview` per language** — each with its own `question_name`, language-specific `interview_guide` (or piped content), and matching `language` in `text_interview_config` / `voice_interview_config`.
3. Use **skip / navigation rules** so each respondent reaches only the interview for their language.
4. **Apply the schema** — pass it as `humanize_schema=schema` on deploy, or patch it onto a live survey. Skip routing alone is not enough: without the schema, every forked interview keeps the default English text-mode config.

```python
from pathlib import Path
from edsl import QuestionMultipleChoice, QuestionInterview, Survey

q_lang = QuestionMultipleChoice(
    question_name="interview_language",
    question_text="Which language should we use for the interview?",
    question_options=["English", "Spanish", "French"],
)

guide_en = Path("interview_guide_en.md").read_text(encoding="utf-8")
guide_es = Path("interview_guide_es.md").read_text(encoding="utf-8")
guide_fr = Path("interview_guide_fr.md").read_text(encoding="utf-8")

q_en = QuestionInterview(
    question_name="depth_en",
    question_text="Understanding your experience",
    interview_guide=guide_en,
)
q_es = QuestionInterview(
    question_name="depth_es",
    question_text="Entender su experiencia",
    interview_guide=guide_es,
)
q_fr = QuestionInterview(
    question_name="depth_fr",
    question_text="Comprendre votre expérience",
    interview_guide=guide_fr,
)

survey = (
    Survey([q_lang, q_en, q_es, q_fr])
    .add_skip_rule("depth_en", "{{ interview_language.answer }} != 'English'")
    .add_skip_rule("depth_es", "{{ interview_language.answer }} != 'Spanish'")
    .add_skip_rule("depth_fr", "{{ interview_language.answer }} != 'French'")
)

schema = {
    "questions": {
        "depth_en": {
            "interview_mode": "both",
            "text_interview_config": {"language": "english"},
            "voice_interview_config": {"language": "english"},
        },
        "depth_es": {
            "interview_mode": "both",
            "text_interview_config": {"language": "spanish"},
            "voice_interview_config": {"language": "spanish"},
        },
        "depth_fr": {
            "interview_mode": "both",
            "text_interview_config": {"language": "french"},
            "voice_interview_config": {"language": "french"},
        },
    }
}

# Required: apply language (and mode) config — otherwise forks default to English text.
info = survey.humanize(
    human_survey_name="Multilingual depth interview",
    humanize_schema=schema,
)
# Live survey already deployed without the right languages:
# Coop().patch_human_survey_humanize_schema(info["uuid"], schema)
```

**Case sensitivity — two different conventions:**

| Where | Casing | Example |
|-------|--------|---------|
| MC `question_options` and skip-rule literals | Must match **exactly** (including capitalization) | `'English'`, not `'english'` |
| Schema `language` ids | Always **lowercase** | `english` / `spanish` / `french` |

A skip rule that compares against `'english'` when the option is `"English"` will never match, and the respondent can land on the wrong interview (or none). Schema ids stay lowercase regardless of how you label the MC options.

Keep the set of languages finite and known at deploy time. Prefer language-specific guides when probes and framing matter; a shared English guide plus a schema `language` alone is weaker for non-English fielding. For skip-rule syntax → **edsl:edsl-surveys**. For structured (non-interview) multi-language wording, keep using Jinja if/then on a single question — do not fork those.

## Guide alignment

The `interview_guide` can stay in the language you wrote it in; the interview layer handles interaction (spoken for voice, written for text) in the configured language. For non-English fielding, guide content and probes should match the configured language. Research interview design is covered by **ep-agent:research-interview-design**.
