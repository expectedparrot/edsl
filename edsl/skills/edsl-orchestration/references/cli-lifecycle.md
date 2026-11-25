# Orchestration CLI lifecycle

All commands accept portable `WorkflowExperiment` JSON created with
`experiment.save("experiment.json")`. The namespace is `ep orchestration` to
distinguish respondent orchestration from the separate `ep workflow` task-gate
commands.

## Validate, inspect, and run

```bash
ep orchestration validate --file experiment.json
ep orchestration inspect --file experiment.json
ep orchestration run --file experiment.json --output run/
```

`validate` checks the workflow, participants, state maps, and executor bindings.
`inspect` summarizes steps, questions, assignments, dependencies, state maps,
and executor routes. Neither command makes model calls.

`run` advances scripted and configured LLM work. LLM executors may make
provider calls. To replay non-scripted work without model calls, supply a JSON
array of rows with `step`, `participant`, and `answers` keys:

```json
[
  {"step": "propose", "participant": "Amina", "answers": {"activity": "A hike"}},
  {"step": "approve", "participant": "Boris", "answers": {"approved": "Yes"}}
]
```

Pass it using `--responses responses.json`. Scripted executors use the literal
answers embedded in the experiment. On a replay-driven resume, pass the same
answer file again so the run does not switch back to configured LLM execution.
Resume with the same experiment, output directory, and `--instance-id`:

```bash
ep orchestration run --file experiment.json --output run/ --responses responses.json --resume
```

The default instance ID is `experiment`. The run directory holds the pinned
`experiment.json`, workflow and state databases, and `completion.json` after a
declared pause or completion. Use a new or empty output directory for a new run.

## Humanize delivery

Start a fresh all-human experiment without sending invitations:

```bash
ep orchestration start --file experiment.json --output human-run/
ep orchestration status --output human-run/
```

The start command requires every participant to resolve to the `human`
executor and every Agent to have a non-empty `email` trait. It creates a pinned
experiment and `run.json` manifest. It refuses a non-empty output directory.

After the user has authorized sending invitations and Expected Parrot
authentication is configured, call `sync`:

```bash
ep orchestration sync --output human-run/
```

Each `sync` call sends currently ready Humanize surveys, imports completed
responses, and dispatches newly unlocked work. Call it again to check for later
responses. `status` reports the instance status, item IDs, participant IDs, step
names, item states, and event count. The CLI does not yet support mixed human
and LLM delivery, a generic Humanize configuration, or arbitrary delivery
adapters.
