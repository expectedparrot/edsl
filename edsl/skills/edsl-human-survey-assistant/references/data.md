# Survey assistant data

What a survey with the assistant records, where each piece is, and how they connect.

## Contents

- [Where to look](#where-to-look)
- [Summary](#summary)
- [Conversations](#conversations)
- [Supplementary downloads](#supplementary-downloads): messages, turns, edits, threads,
  pages, configs
- [The interaction trace](#the-interaction-trace)
- [How they connect](#how-they-connect)
- [Gaps and odd rows](#gaps-and-odd-rows)
- [Conversations in the browser](#conversations-in-the-browser)
- [Common questions](#common-questions)

## Where to look

Start with the **[summary](#summary)**, then the **[conversations](#conversations)**:
each respondent's survey as the owner's Assistant tab shows it, with the chat, the
assistant's edits and the respondent's own answers in the order they happened. Fetch
another download only when the summary or the conversations raise a question they
can't answer:

- **[`turns`](#turn-fields):** when the summary shows failed replies and the
  researcher needs to know why (`error`); or when asked how fast the assistant
  replied or what a reply cost (`sent_at`, `first_text_at`, `credits`).
- **[`edits`](#edit-fields):** when analyzing the assistant's edits by question
  across respondents, each with its final outcome (which questions it filled most,
  which it was refused on, which were undone), or the summary's `edits.rejected` is
  above 0 and the researcher wants to know why.
- **[`threads`](#thread-fields):** when comparing respondents who chatted with those
  who didn't, or joining assistant use to the results. It's the only list that
  includes respondents offered the assistant who never chatted.
- **[`configs`](#config-fields) and [`pages`](#page-fields):** when `settings_versions`
  is above 1 (to see which respondents got which settings); when asked what the
  assistant was told; or when the chat didn't appear for someone or couldn't fill a
  question (`hidden_by`, `not_fillable`).
- **[The interaction trace](#the-interaction-trace):** only for what conversations
  leave out: whether a session is `truncated` (`session_state`), when typing began
  (`first_change_at`), when a reply's first words appeared (`first_text_at`), or when
  a row reached the server (`received_at`). Check `trace.rows` in the summary first,
  and fetch it per response or to a file.
- **[`messages`](#supplementary-downloads):** almost never. Only for one turn's
  conversation (`turn=`) without fetching a whole response.

The final answers are in the survey's results (`edsl:edsl-human-survey`).

Every download leaves out previews unless `include_previews=True`
(`--include-previews`), and then marks them `is_preview`.

## Summary

The survey's assistant data in numbers, to decide what to fetch next.

```bash
ep humanize assistant summary <human-survey-uuid>
```

| Field | Meaning |
|---|---|
| `respondents` | `responses`; those `offered` the assistant; those who `chatted`. The share who chatted is out of `offered`. |
| `turns` | `listed`; `pending` (still replying, or ended in the last few seconds); by `status`; replies the respondent saw `ended` as `stopped`, `dropped` or `refused`; `respondents_with_failed` |
| `edits` | The assistant's edits `sent`, by `outcome`, and `rejected` |
| `trace` | The trace's `rows`, `sessions` and `truncated_sessions`: its size before fetching it |
| `settings_versions` | Versions of the assistant's settings, question overrides aside. Above 1: they changed during fielding. |
| `credits` | What the turns cost. Only present for the survey's owner. |
| `as_of`, `last_activity_at` | When it was read, and the latest activity of a response offered the assistant |

## Conversations

Each respondent's survey in the order it happened, one row per thing: pages shown and
submitted, each save of an answer they typed, their messages and the replies, the
answers the assistant filled, had refused or had undone. Built from the trace, the
messages and the edits.

```bash
ep humanize assistant conversations <human-survey-uuid> --output conversations.jsonl
ep humanize assistant conversations <human-survey-uuid> --response <response-uuid>
```

- Grouped by response, responses in the order they were first opened; within one, by
  `position`.
- Flat, not nested: one respondent's conversation is every row with their
  `response_uuid`, together and already in order. Fetch only one with
  `response_uuid=` (`--response`); from a whole survey, filter on `response_uuid`, or
  take each in turn with `df.groupby("response_uuid", sort=False)`.
- `--output` is required unless `--response`: rows hold what respondents wrote.
- A turn is listed a few seconds after it ends. While a survey is live, fetch again
  for newer ones; rows placed by their turn (below) can move once the trace arrives.

Every row has:

| Field | Meaning |
|---|---|
| `response_uuid`, `is_preview` | The response, and whether it was a preview |
| `position` | Its place in the response's rows, from 0 |
| `kind` | What it is (below) |
| `at` | When (UTC): the respondent's clock on rows from the trace, the server's on the rest |
| `page_id` | The page |
| `turn` | The message and reply it belongs to; null for pages and the respondent's own answers |
| `session`, `seq` | The trace row it came from; null on rows placed by their turn |
| `placed` | `trace`; or, when the trace lacked it (a closed tab, a lost batch), placed by its turn: `after_message`, `before_reply` or `end` |

By `kind`:

| `kind` | Fields |
|---|---|
| `page_shown`, `page_submitted` | `page_key` |
| `answer` | A save of an answer the respondent typed: `question`, `value`, `draft_type`, `draft_version`, `saved` (what closed it, the trace's `closed_by`), `changes`, `draft_write`, `value_omitted`, `chars` |
| `message` | `text`; null until its turn is listed |
| `message_refused` | `refused`: why the message was turned away. It has no turn. |
| `assistant_edit` | An answer the assistant filled: `edit`, `question`, `value`, `draft_type`, `draft_version`, `outcome`, `reason`, `draft_write` |
| `edit_undone` | The respondent pressed Undo: `edit`, `question`, and the `value` the answer went back to |
| `edit_rejected` | An answer the assistant asked for that was refused: `edit`, `question`, `value`, `draft_type`, `draft_version`, `rejection`. It never showed in the chat. |
| `reply` | `text`; `status`, how the turn ended, as on `turns` (`complete`, `interrupted`: stopped or cut off, the text what had arrived; or `failed`); `ended`, how the respondent saw it end (`stopped` is their Stop, `dropped` a lost connection), null if their browser never said; `error_kind`; `notice`, what a failed reply told them |
| `not_recorded` | Something that couldn't be recorded: `question`, `rejected_type`, `reason`, `chars` |

- An `assistant_edit`'s `outcome` is what the form did then: `applied`; `skipped`,
  with `reason` (`field_changed`, `page_changed`, `time_up`, `invalid`); or `sent`
  when the respondent's browser never said. An Undo is a later `edit_undone` row.
- Rows are things that happened, not final states. Each edit's final outcome is in
  `edits`.
- `rejection` has `reason`, `message`, and `violations` when the value broke the
  question's rules.
- `value` is the answer at that moment, in the shape `draft_type` and `draft_version`
  name. `value_omitted` is true for a value too long to keep, with its length in
  `chars`.
- `draft_write` is about when the row reached the server, not about the form: see the
  [trace](#each-type). Don't use it to decide whether a change counted.

## Supplementary downloads

For what conversations don't cover. Conversations join the trace, `messages` and
`edits`; each can be fetched on its own. `turns`, `threads`, `pages` and `configs`
aren't in conversations at all.

Each takes the same filters as conversations; `messages` and `edits` also take
`turn=<turn>` for one turn. From the command line, `--all` fetches everything and
requires `--output`.

```bash
ep humanize assistant edits <human-survey-uuid> --all --output edits.jsonl
ep humanize assistant turns <human-survey-uuid> --all --output turns.jsonl
ep humanize assistant messages <human-survey-uuid> --turn <turn>
```

- **`messages`:** what the chat showed, one row per part, in the order turns ended:
  `respondent_message`, `assistant_text` (with `status`), `edit_receipt` (an answer it
  filled, where it showed in the reply: `edit` and `question`) and `notice` (a failed
  reply's message, with `error_kind`). Each turn's rows are numbered by `seq`, and
  carry `turn_status`, how the turn ended. An `assistant_text`'s `status` is about
  that text only: a turn can be `interrupted` after all its text arrived.
- **`edits`:** one row per answer the assistant asked to fill, rejected ones included,
  with its final outcome.
- **`turns`:** one row per message the assistant answered: how it ended, timing, tokens,
  cost. No text.
- **`threads`:** one row per respondent offered the assistant, chatted or not.
- **`pages`:** one row per page served with the assistant on. A page is
  `response_uuid` and `page_id` together.
- **`configs`:** the settings each page ran on.

```bash
ep humanize assistant threads <human-survey-uuid> --all --output threads.jsonl
ep humanize assistant pages <human-survey-uuid> --all --output pages.jsonl
ep humanize assistant configs <human-survey-uuid> --all --output configs.jsonl
```

### Turn fields

| Field | Meaning |
|---|---|
| `turn`, `response_uuid`, `thread`, `is_preview`, `page_id` | The turn, its response and conversation, whether it was a preview, and the page |
| `status` | How the reply finished: `complete`, `interrupted` (stopped or cut off) or `failed` |
| `ended` | How the respondent saw it end, as `chat.reply_ended`'s `status`: `stopped` is their Stop, `dropped` a lost connection; null if their browser never said |
| `sent_at`, `finished_at` | When the message arrived and the reply finished (UTC) |
| `first_text_at`, `ended_at` | When the first words and the end reached the respondent, by their clock; null if never reported |
| `model`, `calls`, `retries` | The model, how many calls the reply took, and how many were retries |
| `input_tokens`, `cached_input_tokens`, `output_tokens`, `reasoning_tokens`, `usage_estimated` | Tokens across the turn's calls; `cached_input_tokens` is part of `input_tokens` |
| `edits`, `rejected_edits` | How many answers it put in the form, and how many it asked for that were rejected |
| `error` | A failed turn's `kind`, `stage`, `message`, `retryable`, `at`, and for some kinds `http_status`, `input_tokens` and `limit`, `reason` or `error_code` |
| `credits` | What the turn cost. Only present for the survey's owner. |

Time to first words: `first_text_at − sent_at`, mixing the respondent's clock with the
server's, so treat it as approximate.

### Edit fields

| Field | Meaning |
|---|---|
| `edit`, `turn`, `response_uuid`, `is_preview`, `page_id` | The edit, the turn that asked for it, its response, whether it was a preview, and the page |
| `question`, `value`, `draft_type`, `draft_version` | The question and the answer asked for |
| `server_outcome` | `sent` (put in the form) or `rejected` |
| `rejection` | Why it was rejected, as in conversations |
| `outcome`, `reason` | Whether the form took a sent edit, as it stands: `applied`; `skipped`, with `reason`; `undone` (the respondent pressed Undo); or `sent` when their browser never said. It can change until the page is submitted, and stays `applied` when the respondent later typed over the answer: see "Were they kept?" below. Null for a rejected edit. |
| `at` | When the server checked it (UTC): when a sent edit went to the form, or a rejected one was refused |

### Thread fields

| Field | Meaning |
|---|---|
| `thread`, `response_uuid`, `is_preview` | The conversation, its response, and whether it was a preview |
| `response_status` | The response's status |
| `offered_at`, `last_activity_at` | When the assistant was first offered, and the response's latest activity (UTC) |
| `turns` | Turns listed for it; 0 if the respondent never chatted |
| `trace_state` | The trace's state for the response: `complete`, `truncated` or `unknown` |
| `credits` | What its turns cost. Only present for the survey's owner. |

### Page fields

| Field | Meaning |
|---|---|
| `response_uuid`, `page_id`, `is_preview` | The page, and whether it was a preview |
| `page_key`, `questions` | The page's group (or question) name, and its questions |
| `status`, `served_at`, `closed_at` | `open`, `submitted` or `replaced` (the survey was edited while open), and when |
| `config` | The config its turns ran on |
| `chat_shown`, `hidden_by` | Whether the chat was shown, and why not |
| `fillable_questions`, `not_fillable` | What the assistant could fill, and the rest with why not |

### Config fields

| Field | Meaning |
|---|---|
| `config`, `first_served_at`, `pages` | The config, when first served, and how many pages ran on it |
| `settings` | The settings as served: `role`, `model`, `name`, `presentation`, `system_prompt`, `can_fill_answers`, `question_overrides`. Pages with different question overrides have different configs, so compare `settings` without `question_overrides` to find a change during fielding. |

## The interaction trace

One row per step a respondent took, on surveys with the assistant on: what
conversations are ordered by, with fields they leave out. It holds no message text.
It's the largest download: fetch it per response or to a file.

```bash
ep humanize interactions <human-survey-uuid> --all --output interactions.jsonl  # or .json
ep humanize interactions <human-survey-uuid> --response <response-uuid> --all -o one.json
ep humanize interactions <human-survey-uuid> --count
```

- `--all` requires `--output`: rows hold respondents' answers as they typed them.
- For analysis, download it once fielding has ended.

### Every row

| Field | Meaning |
|---|---|
| `id` | The row's id |
| `response_uuid` | The response; join to results on this |
| `is_preview` | From a preview link |
| `session` | The page load it was recorded in; a reload starts a new one |
| `session_started_at` | When that page load was served, by the server's clock (UTC). Orders a response's sessions. |
| `seq` | Position in its session. Order a session's rows by this, not by time. |
| `session_state` | `complete`, `truncated` (rows known to be missing) or `unknown` |
| `at` / `received_at` | The respondent's clock / when Expected Parrot received it (UTC) |
| `type` | One of the types below |
| `actor` | `respondent`, `assistant` or `platform` |
| `page_id` | The page. A page is identified by `response_uuid` and `page_id` together. |

### Each type

| `type` | Fields |
|---|---|
| `page.shown`, `page.submitted` | `page_key`: the group's name, or the first question's name when pages hold one question |
| `form.edited` | The respondent changed an answer: `question`, `value`, `draft_type`, `draft_version`, `change_count`, `first_change_at`, `closed_by`, `draft_write`, `value_omitted`, `chars` |
| `chat.message_sent` | `turn` (the reply's id), or `refused` (why the message was refused), or neither if it never arrived |
| `chat.reply_ended` | `message_seq`, `turn`, `status` (`complete`, `interrupted`, `failed`, `stopped`, `refused`, `dropped`), `connection`, `first_text_at`, `error_kind` |
| `assistant.edit_applied` | The assistant filled an answer: `question`, `edit`, `value`, `draft_type`, `draft_version`, `draft_write`, `value_omitted`, `chars` |
| `assistant.edit_undone` | The respondent pressed Undo. Same fields; `value` is what the answer went back to. |
| `assistant.edit_skipped` | A filled answer that couldn't be put in the form: `question`, `edit`, `reason` (`field_changed`, `page_changed`, `time_up`, `invalid`) |
| `runtime.event_rejected` | Something that couldn't be recorded: `question`, `rejected_type`, `reason`, `chars` |

- `value` is the answer in the form at that moment, in the shape `draft_type` and
  `draft_version` name.
- `draft_write` is about when the row arrived, not about the form: `applied` (saved as
  the in-progress answer), `superseded` (a later change from the same tab had already
  arrived) or `late` (the page had already been submitted). A `late` or `superseded`
  row can still be a change the respondent made and submitted. Don't use it to decide
  whether a change counted: use the row's `type`, the edit's `outcome` and the results.
- `value_omitted` is true for a value too long to keep; the change is still recorded,
  with its length in `chars`.
- A `truncated` session is missing rows: say so in any analysis that relies on
  complete sequences, rather than treating the gap as inactivity.

## How they connect

- `response_uuid` is on every row, and joins each of them to the results.
- `turn` names one message and the assistant's reply to it: on conversation rows,
  `turns`, `messages` and `edits`, and on the trace's `chat.message_sent` and
  `chat.reply_ended` rows.
- `edit` names one answer the assistant asked to fill: on conversations'
  `assistant_edit`, `edit_undone` and `edit_rejected` rows, receipts, `edits`, and the
  trace's `assistant.edit_*` rows.
- A conversation row from the trace has its `session` and `seq`.
- A page is `response_uuid` and `page_id` together.
- A message the server refused has no turn and no text.
- While a survey is live, a `turn` named in the trace can be missing from the others
  for a few seconds, or longer if the respondent left mid-reply: fetch again later
  rather than treating it as lost.

Order within one response:

| Download | Order |
|---|---|
| Conversations | Already grouped by response and in order |
| `threads`, `pages`, `configs` | In the order they began or were served |
| `messages`, `turns`, `edits` | Interleaved across responses; one response's rows are already in order |
| The trace | Interleaved, and arrives out of order when a batch is sent late: sort by `session_started_at`, then `seq` |

## Gaps and odd rows

What a conversation row that looks wrong usually means, and how to check before
reporting it:

| What you see | What it means | How to confirm |
|---|---|---|
| `reply` placed `after_message`, `ended` null | The tab closed or the respondent left mid-reply: their browser never reported the end | The session's `session_state` in the trace, often `truncated`; the turn's `ended` is null in `turns` too |
| `message` placed `before_reply` | A batch of the respondent's events was lost; the reply's end arrived | That session's `session_state` is `truncated` |
| `assistant_edit` with `outcome` `sent` | The answer went to the form, but the browser never said whether it took | The edit's `outcome` is `sent` in `edits`; the session is usually `truncated`, or the tab closed |
| `assistant_edit` placed `after_message`, `applied`, just before its `edit_undone` | The record of the fill was lost, but its Undo arrived, so the form took it | The edit's `outcome` is `undone` in `edits`; the session is `truncated` |
| A response's rows all placed `end`, with no page rows | No trace for the response at all | Its thread's `trace_state` is `unknown` |
| `message` or `reply` with `text` and `status` null | The turn isn't listed yet: still settling, or paused and abandoned | `turns.pending` in the summary; fetch again later. Still null long after fielding: an abandoned turn. |
| `reply` with `status` `failed` | The assistant errored; the respondent saw `notice` | `error` on that turn in `turns` |
| `reply` with `status` `interrupted` | The reply was cut short | Its `ended`: `stopped` is their Stop, `dropped` a lost connection |
| `message_refused` | The server turned the message away | `refused` says why |
| `edit_rejected` | The assistant asked to fill something it couldn't | `rejection.reason` |
| `assistant_edit` with `outcome` `skipped` | The form couldn't take the edit: the field changed, the page moved on | `reason` |
| `not_recorded` | An event the server couldn't store, such as a value too large | `reason`, `chars` |
| `answer` with `draft_write` `late` | The save reached the server after the page closed. Not an error: it can still be what was submitted. | The submitted answer is in the results |

Say how many respondents each affects, and whether it matters for the analysis,
rather than dropping them.

## Conversations in the browser

`Coop().get_human_survey_assistant_url(uuid)` is the survey's **Events** page,
**Assistant** tab: one conversation per respondent offered the assistant, whether or
not they chatted, with which answers it filled and how each ended; each downloads as
JSON. Preview conversations are listed too, with a **Preview** badge.

## Common questions

- **Did a respondent use the chat?** Their thread's `turns` above 0. Respondents with
  no thread were never offered it.
- **Did the assistant work for a respondent?** Their `reply` rows: `status` `failed`
  (with the `notice` they saw) or `interrupted`, and a `message` with no reply after
  it. A respondent whose replies failed didn't get the assistant as designed; tell the
  researcher before they compare conditions. Whether a cut-short reply was their Stop
  or a dropped connection is the reply's `ended`.
- **Which answers did the assistant fill, and were they kept?** `assistant_edit` rows
  with `outcome` `applied`, then any later `edit_undone` for that `edit`, or `answer`
  row for that `question`, in the same response. The submitted answer is in the
  results.
- **What did the assistant try to fill but couldn't?** `edit_rejected` rows (and
  `rejection`), and `assistant_edit` rows with `outcome` `skipped` (and `reason`).
  Across respondents by question: `edits`.
- **What did respondents change by hand?** `answer` rows.
- **What did it cost?** The summary's `credits`. After a pilot, scale by the planned
  sample for an estimate.
- **Did the assistant change during fielding?** `settings_versions` above 1 in the
  summary; `configs` has each version, and `pages` which pages ran on which.
