# Checking survey routes

Write examples from the research brief before implementing its skip or stop rules. Each `expected_path` lists every question this respondent should see, in order, through the end. For a survey with consent and two follow-up routes, save a file named `paths.json`:

```json
{
  "cases": [
    {"name": "declines", "answers": {"consent": "No"}, "expected_path": ["consent"]},
    {"name": "needs help", "answers": {"consent": "Yes", "rating": 0}, "expected_path": ["consent", "rating", "urgent", "closing"]},
    {"name": "just above cutoff", "answers": {"consent": "Yes", "rating": 3.5}, "expected_path": ["consent", "rating", "routine", "closing"]}
  ]
}
```

```bash
ep surveys check-paths survey.ep --cases paths.json
```

Supply answers for visited questions used in routing rules. Other answers are optional. Optional `scenario` and `agent` objects provide values for context-dependent rules. The checker uses only answers from questions reached so far and verifies the end of the interview. A mismatch returns exit code 5 and the first divergence for each failing case in `error.details`. For example, a broad fallback might send the “needs help” respondent from `rating` to `routine` when the brief requires `urgent`. Correct the rule and rerun the cases.

The check walks local, question-level skip and stop rules without inference. It compares question names in the survey’s fixed order. Use `--schema` and `--paths` for grouped browser pages. Job-level order and sampling policies require assignment-level tests. A rule expression that draws a random value can take a different path on a later run.
