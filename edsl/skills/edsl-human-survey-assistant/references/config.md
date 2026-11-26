# Survey assistant configuration

Everything under `survey.assistant` in the humanize schema. Omit the block for no
assistant.

## Fields

| Field | Default | Meaning |
|---|---|---|
| `enabled` | `False` | Whether the assistant is shown. `False` keeps the configuration but switches it off. |
| `name` | `"Assistant"` | The name shown on the chat, up to 60 characters. |
| `role` | `"express_intent"` | `"express_intent"` or `"advise"` (SKILL.md §1). |
| `presentation` | required | How the chat is shown. Required even with `enabled: False`. |
| `system_prompt` | none | Private instructions, up to 20,000 characters: who the respondents are, the study's terms, what to avoid. Added to the role's rules. |
| `can_fill_answers` | `True` | `False` for an assistant that only explains. |
| `model` | the default | Leave out. Only the default is accepted. |
| `question_overrides` | none | Per-question exceptions, by question name (below). |

### `presentation`

| Field | Meaning |
|---|---|
| `type` | `"sidebar"`: the chat beside the form. `"modal"`: a button that opens a chat window. Both open as a drawer on phones. |
| `empty_state.heading` | Heading before the first message, up to 120 characters. Defaults to "Need help answering?" (`express_intent`) or "Need help deciding?" (`advise`). |
| `empty_state.placeholder` | Message box placeholder before the first message, up to 120 characters. |
| `reply_placeholder` | Message box placeholder once the conversation has started, up to 120 characters. Defaults to "Reply". |

### `question_overrides`

Every field defaults to on, so write only the ones being turned off. A survey message
(instruction) accepts only `chat`. A name that isn't in the survey has no effect.

| Field | Default | Meaning |
|---|---|---|
| `fillable` | `True` | `False`: the assistant can't fill this question, but can still explain it. |
| `chat` | `True` | `False`: no chat on the page holding this question. |
| `context` | `True` | `False`: the page holding this question is left out of what the assistant knows on later pages: its questions, answers and any conversation on it. |
| `instructions` | none | Private instructions for this question, up to 4,000 characters, given while it is on screen. |

Under `"group"` presentation, `chat` and `context` apply to the whole page: one
question with `chat: False` hides the chat for every question on its page.

`context: False` doesn't keep information secret, since a respondent can type it into
the chat. It stops the assistant knowing it and bringing it up.

## What it can fill

With `can_fill_answers` on: `multiple_choice`, `likert_five`, `yes_no`,
`linear_scale`, `multiple_choice_with_other`, `checkbox`, `checkbox_with_other`,
`top_k`, `rank`, `numerical`, `numerical_range`, `free_text`, `edit`, `email`,
`list`, `budget`, `matrix`, `distribution`, `url`.

For `edit`, it always fills in the whole revised text, starting from `text_to_edit`,
never just the changes.

It explains, but never fills:

- date, date and time, demand, dict and dropdown questions, file uploads and
  interviews (the chat isn't shown on interview pages);
- questions the server answers itself, such as compute and image generation;
- questions with two options (or matrix rows, or distribution outcomes) that read the
  same, since a filled answer couldn't say which it meant;
- questions set to `fillable: False`.

## Limits

- Respondents' messages: 16,000 characters.
- The conversation carries over from page to page, and the assistant sees earlier
  answers, except pages set to `context: False`.
