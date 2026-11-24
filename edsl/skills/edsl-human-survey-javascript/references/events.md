# Retrieving human survey events

Events are what scripts record with `ep.log`. They are retrieved oldest first.
Events from preview links are left out unless asked for with `include_previews=True`
(`--include-previews`), and then marked `is_preview`: use that while testing a
script, and leave it off for analysis.

## Everything

```bash
ep humanize events <human-survey-uuid> --all --output events.jsonl   # or .json
ep humanize events <human-survey-uuid> --all --include-previews --output preview-events.jsonl
```

`--all` requires `--output`: event payloads can hold whatever a script logged, so a
whole log goes to a file, written privately and only once the download completes.

## Only what's new

Pass the `id` of the last event downloaded, with the same `include_previews`:

```bash
ep humanize events <human-survey-uuid> --all --after <next_cursor> --output new.jsonl
```

The CLI prints `next_cursor` with every result; pass it back as `--after`.

**Use this for monitoring only.** Fetching only new events while a survey is still
collecting can occasionally miss an event that was still being saved. For analysis,
do one full download once fielding has ended, at least an hour after the last
response (events can still arrive for up to an hour after a response completes).

## One batch, and counting

- `ep humanize events <uuid>` prints the first batch. Pass its `next_cursor` as
  `--after` to continue; use `--limit` to set batch size.
- `coop.count_human_survey_events(uuid)` / `ep humanize events <uuid> --count` gives
  the number of events without downloading them, with the same `include_previews`. It is a count at that moment; a
  survey still collecting will have more by the time a download finishes.

## Event fields

| Field | Meaning |
|---|---|
| `id` | The event's unique id; also the cursor for `after` |
| `received_at` / `client_ts` | When Expected Parrot received it / when the browser logged it (UTC) |
| `response_uuid` | The response it belongs to; join to responses on this |
| `is_preview` | From a preview link; only present in a download with `include_previews` |
| `log_session_uuid` | The page load it was logged in; a reload starts a new session |
| `session_state` | `complete`, `truncated` (events known to be missing), or `unknown` (the session never signalled its end) |
| `client_seq` | Position within its session, from 0; a gap means an event wasn't recorded |
| `question_name` | The question whose script logged it |
| `event_name` / `payload` | What was passed to `ep.log` |
| `hook_event` | The hook that was running, e.g. `question.ready` |
| `event_type` / `source` | Always `ep.log` / `author_script` for now |

Order events within a session by `client_seq`, not by timestamp.
