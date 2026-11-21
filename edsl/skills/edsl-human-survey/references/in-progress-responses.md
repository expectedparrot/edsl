# In-progress responses

By default, `ep humanize responses` returns completed responses only. To also get
responses that are still being taken
(for dropout, attrition, or checking a survey that is still running):

```bash
ep humanize responses <uuid> --include-partial --output data/human_responses.ep
```

The underlying response API also supports `started_after` and `started_before`
filters when called programmatically.

## Reading them

- Every result has `agent.response_status` (`complete` or `in_progress`) and
  `agent.last_activity_at` (when the respondent last moved forward; use it to tell
  someone mid-survey from someone who left).
- An in-progress response holds only the answers submitted so far; the rest read
  as `None`. Filter to `agent.response_status == "complete"` before computing
  anything that assumes a finished survey (`n`, means, comparisons).
- An in-progress response can come back later with more answers, or as complete.
  When combining downloads, keep the latest row per `agent.response_uuid`.
- Say in the write-up whether partials were included, and how many.

## Counts

`ep humanize status <uuid>` reports `n_complete` and `n_in_progress` separately.
Use `n_complete` to decide whether a
survey has reached its target sample.
