# Portable asset-market pilot

Requires EDSL from the updated shared-state branch, with the standard
`call_market_submit@1` and `call_market_settle@1` capabilities and workflow
pause support. No experiment-specific Python files are required for execution.

From this directory, replay the saved decisions without model calls:

```sh
python -m edsl.workflows.replay --experiment experiment.json \
  --responses responses.json --output replay
python -m edsl.workflows.replay --experiment experiment.json \
  --responses responses.json --output replay --resume
```

The first command pauses at round 12. The second pauses at round 17 after two
consecutive prices above $17.50. The economic horizon stays at 30, and no shares
are redeemed at either observation pause.

- `experiment.json`: complete workflow, participants, model settings, economic
  rules, state definitions, and pause/continuation conditions.
- `responses.json`: 204 original trader responses.
- `expected.json`: original accounts, transaction tape, and admitted orders.
- `verification.json`: exact replay comparison and test results.

All serialized rules are interpreted by EDSL; no source-code callbacks are
embedded or imported from the example. `WorkflowExperiment.load()` rejects
missing runtime capabilities before creating execution databases. This is a
retrospective encoding of the original exploratory observation policy, whose
extension was declared after round 6.
