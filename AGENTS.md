# Agent Guide: EDSL CLI

This guide is for coding agents and automation using the EDSL command line. Use `ep` in examples. `edsl` and `python -m edsl` are equivalent entry points when `ep` is not installed.

## Operating Model

The CLI is designed for programmatic use.

- Stdout is a single JSON document.
- Stderr is for diagnostics and logs.
- Commands should not prompt interactively.
- Always parse stdout as JSON and inspect `status`.
- Read `warnings`; lower-level output may be captured there to preserve the JSON envelope.
- Do not scrape prose, progress lines, URLs, or table output from stdout.
- Prefer `.ep` packages for durable EDSL objects.

Success envelope:

```json
{
  "status": "ok",
  "data": {},
  "warnings": []
}
```

Error envelope:

```json
{
  "status": "error",
  "error": {
    "code": "USAGE_ERROR",
    "message": "What failed",
    "suggestion": "What to try next"
  }
}
```

Exit codes:

| Code | Meaning |
| --- | --- |
| `0` | Success |
| `1` | General error |
| `2` | Usage error |
| `3` | Resource not found |
| `4` | Authentication error |
| `5` | Validation error |
| `6` | Remote service error |

## First Commands To Run

Start by discovering the installed CLI rather than guessing flags.

```bash
ep --help
ep info
ep run --help
ep jobs --help
ep results --help
ep schema list
```

`ep info` reports version and configuration diagnostics and redacts credentials.

## Command Inventory

Top-level commands available in the CLI:

| Command | Purpose |
| --- | --- |
| `agents` | Create or transform `AgentList` objects. |
| `auth` | Manage authentication. |
| `balance` | Show Expected Parrot credit balance. |
| `check` | Check Expected Parrot URL and API key connectivity. |
| `clone` | Clone a shared object into a local `.ep` package. |
| `costs` | Track estimated and actual job costs in a ledger. |
| `credits` | Open or return the Expected Parrot credits page. |
| `delete` | Delete a remote object. |
| `humanize` | Create and manage human surveys. |
| `info` | Show version, config, and diagnostics. |
| `inspect` | Inspect local packages/files or remote objects. |
| `jobs` | Manage remote jobs. |
| `metadata` | Read object metadata. |
| `models` | List models or create `ModelList` files. |
| `objects` | Namespace for remote object commands. |
| `open` | Render/open an object as HTML. |
| `profile` | Show authenticated profile. |
| `profiles` | Manage local environment profiles. |
| `pull` | Pull latest remote object data into a package. |
| `push` | Push or patch an object on Expected Parrot. |
| `results` | Query and export `Results`. |
| `run` | Run jobs/questions. |
| `scenarios` | Create or transform `ScenarioList` objects. |
| `schema` | Introspect object and question schemas. |
| `search` | Search shared Expected Parrot objects. |
| `settings` | Show remote EDSL settings and rate-limit diagnostics. |
| `share` | Share an object with a user. |
| `shared` | List users an object is shared with. |
| `surveys` | Create and edit `Survey` objects. |
| `unpack` | Unpack a `.ep` package for inspection. |
| `unshare` | Remove user access to an object. |
| `unzip` | Alias for `ep unpack`. |
| `update-metadata` | Update remote metadata without object changes. |
| `validate` | Validate questions, surveys, and jobs. |

Many remote object commands are available both at top level and under `ep objects`, for example `ep search` and `ep objects search`.

## Schemas And Validation

Use schemas before constructing JSON by hand.

```bash
ep schema show --class Survey
ep schema show --class AgentList
ep schema show --class ScenarioList
ep schema show --class ModelList
ep schema show --class Jobs
ep schema show --class Results
ep schema show --question_type free_text
ep schema show --question_type multiple_choice
ep schema show --question_type linear_scale
```

Validate objects before running them.

```bash
ep validate --file survey.json
ep validate --file jobs.json
ep validate --json '{"type":"free_text","question_text":"Say hi"}'
```

If validation fails, use the JSON error envelope. Do not continue by trying to run the same invalid input.

## Object Formats

The CLI accepts two broad formats:

- JSON serialized objects, usually from `.to_dict()`.
- Git-backed `.ep` packages.

Use `.ep` packages when you need stable files that can be inspected, pushed, pulled, versioned, or reopened. Use JSON for lightweight generated input or one-off tests.

Common object types:

- `Survey`: questions and survey flow.
- `AgentList`: agent traits and instructions.
- `ScenarioList`: scenario data.
- `ModelList`: model selections.
- `Jobs`: complete run specification combining survey, agents, scenarios, and models.
- `Results`: completed run output.

Inspect objects:

```bash
ep inspect survey.ep
ep inspect jobs.ep
ep metadata results.ep
```

## Building Inputs

Prefer creating complete `Jobs` objects when possible. They contain the full execution specification.

Common patterns:

```bash
# Run a single ad hoc question.
ep run --question "What is 2+2?" --model gpt-4o --output results.ep

# Run a saved Jobs package.
ep run jobs.ep --output results.ep

# Run a saved Jobs JSON file.
ep run jobs.json --output results.json

# Run from individual components.
ep run --survey survey.json --agent_list agents.json --scenario_list scenarios.json --model gpt-4o --output results.ep

# Use inline JSON for a small generated question.
ep run --json '{"type":"free_text","question_text":"Say hi"}' --output results.ep

# Pipe JSON.
cat jobs.json | ep run --output results.ep
```

Important replacement rule: component override flags replace the corresponding component in the base job.

- `--agent_list` replaces agents.
- `--scenario_list` replaces scenarios.
- `--model_list` replaces models.
- `--model` replaces models with a single model.
- `--model` and `--model_list` are mutually exclusive.

## Creating Agent Lists

Create `AgentList` objects from tabular data.

```bash
ep agents create --from-csv people.csv --output agents.ep
ep agents create --from-csv people.csv --name-field name --instructions instructions.txt --output agents.ep
ep agents create --from-xlsx people.xlsx --sheet Sheet1 --name-field respondent_id --output agents.ep
ep agents create --from-csv people.csv --codebook '{"age":"Age in years"}' --output agents.json
```

Transform existing agent lists:

```bash
ep agents transform agents.ep --help
```

Use `ep agents create --help` and `ep agents transform --help` for the exact transformation flags.

## Creating Scenario Lists

Create `ScenarioList` objects from CSV, Excel, or image inputs.

```bash
ep scenarios create --from-csv topics.csv --output scenarios.ep
ep scenarios create --from-xlsx topics.xlsx --sheet Sheet1 --output scenarios.ep
ep scenarios create --from-image image1.png --from-image image2.png --output image_scenarios.ep
```

Transform existing scenario lists:

```bash
ep scenarios transform scenarios.ep --help
```

Use `ep scenarios create --help` for supported source types and options.

## Creating And Editing Surveys

Survey commands let agents construct surveys without writing Python.

```bash
ep surveys create --question-type free_text --question-name q0 --question-text "What do you think?" --output survey.ep
ep surveys add-question survey.ep --question-type multiple_choice --question-name q1 --question-text "Pick one." --option A --option B
ep surveys questions survey.ep
ep surveys show survey.ep
ep surveys add-skip-rule survey.ep --question q1 --expression "{{ q0.answer }} == 'skip'"
ep surveys add-stop-rule survey.ep --question q1 --expression "{{ q1.answer }} == 'done'"
ep surveys add-instruction survey.ep --text "Answer as briefly as possible."
ep surveys set-memory survey.ep --help
ep surveys add-question-group survey.ep --help
ep surveys move-question survey.ep --help
ep surveys drop-question survey.ep --help
```

Use `ep surveys review survey.ep` only when a local review UI is appropriate for the task.

## Creating Model Lists

List models with filters, or create a `ModelList`.

```bash
ep models
ep models --service openai
ep models --search gpt --text --sort input-price
ep models --vision --sort name
ep models create --model gpt-4o --output models.ep
ep models create --model gpt-4o --model gpt-4o-mini --output models.ep
ep models create \
  --model-spec '{"model":"claude-opus-4-8","service":"anthropic"}' \
  --model-spec '{"model":"gpt-5.4","service":"openai","parameters":{"reasoning_effort":"high"}}' \
  --output models.ep
```

Prefer `--model` on `ep run` for a one-off single model. Create a `ModelList` when the model set is reused or shared. Repeat `--model` when models share configuration; repeat `--model-spec` when services or parameters differ by model. Do not write a Python helper merely to construct a heterogeneous `ModelList`.

## Running Jobs

Blocking runs must write completed results to a file. Do not expect completed result rows in stdout.

```bash
ep run jobs.ep --output results.ep
```

The stdout envelope remains small:

```json
{
  "status": "ok",
  "data": {
    "results": [],
    "meta": {
      "input_mode": "path",
      "model_count": 1,
      "agent_count": 1,
      "scenario_count": 1,
      "result_count": 1,
      "n": 1,
      "local": false,
      "saved": {
        "path": "results.ep",
        "format": "ep",
        "object_type": "Results"
      }
    }
  },
  "warnings": []
}
```

Rules:

- `ep run jobs.ep` without `--output` should return `USAGE_ERROR`.
- Use `--output results.ep` for a package.
- Use `--output results.json` for serialized JSON.
- Use `--local` to disable remote inference.
- Use `--fresh` to ignore cache.
- Use `--n N` for iterations.
- Use `--progress` only when human-facing progress on stderr is acceptable.

## Background Remote Jobs

Use background mode for long remote work. It submits and returns immediately.

```bash
ep run jobs.ep --background
```

The envelope includes `data.meta.remote_job` when available:

```json
{
  "background": true,
  "job_uuid": "job-uuid",
  "progress_bar_url": "https://...",
  "remote_inference_url": "https://...",
  "remote_cache_url": "https://...",
  "results_uuid": null,
  "results_url": null,
  "error_report_url": null,
  "commands": {
    "status": "ep jobs status job-uuid",
    "results": "ep jobs results job-uuid --output results.ep",
    "errors": "ep jobs errors job-uuid --output error.md"
  }
}
```

Follow up with:

```bash
ep jobs status <job_uuid>
ep jobs results <job_uuid> --output results.ep
ep jobs errors <job_uuid> --output error.md
ep jobs manifest <job_uuid>
ep jobs page <job_uuid> --page 0 --page_size 100
```

To submit and poll in one command:

```bash
ep run jobs.ep --background --wait --poll_interval 10 --timeout 3600 --output results.ep
```

Rules:

- `--background` without `--wait` returns no completed results.
- `--background --output results.ep` is invalid because there is nothing to save yet.
- `--background --wait --output results.ep` is valid; it saves only after completion.
- For later retrieval, use `ep jobs results <job_uuid> --output results.ep`.

## Jobs Commands

Remote job management:

```bash
ep jobs list --status running --page 1 --page_size 20
ep jobs status <job_uuid>
ep jobs wait <job_uuid> --poll_interval 10 --timeout 3600
ep jobs results <job_uuid> --output results.ep
ep jobs errors <job_uuid> --output error.md
ep jobs manifest <job_uuid>
ep jobs page <job_uuid> --page 0 --page_size 100
ep jobs cancel <job_uuid> --yes
ep jobs cost jobs.ep --iterations 3
```

Use `--yes` only when the user explicitly requested the destructive action, such as canceling a job.

## Results Workflow

Operate on saved `Results` files, not inline run output.

```bash
ep results columns --file results.ep
ep results select --file results.ep --column "answer.*" --limit 5
ep results select --file results.ep --column answer.q0 --column agent.age
ep results export results.ep --column "answer.*" --output answers.csv
ep results export results.ep --column answer.q0 --column scenario.topic --output answers.csv
```

Rules:

- Repeat `--column`; do not comma-separate columns.
- `results columns` and `results select` accept `.ep`, `.json`, and `.json.gz`.
- Use `results export` for CSV or other file outputs.
- Keep result-heavy data out of stdout unless a results subcommand intentionally returns a small selected subset.

## Models

Discover available models and capabilities:

```bash
ep models
ep models --service openai
ep models --search gpt
ep models --vision
ep models --no-vision
ep models --text
ep models --no-text
```

Use `--model` for a single model override on `ep run`. Use `--model_list` when you need a serialized `ModelList`.

## Costs

Estimate job cost with `jobs cost`, and record estimated or actual costs in a JSONL ledger with `costs log`.

```bash
ep jobs cost jobs.ep --iterations 3
ep costs log --output costs.jsonl --estimated 1.25 --model gpt-4o --agents 10 --questions 5
ep costs log --output costs.jsonl --actual-from results.ep --note "pilot run"
```

Use cost commands before launching large remote jobs when spend matters.

## Remote Object Workflow

Expected Parrot-backed operations are exposed as top-level task commands. There is no separate user-facing `ep coop` command.

```bash
ep search --query "economics" --page 1 --page_size 20
ep clone <owner>/<alias> --path shared_object.ep
ep metadata shared_object.ep
ep update-metadata shared_object.ep --description "Updated" --visibility public
ep shared shared_object.ep
ep share shared_object.ep --user collaborator@example.com
ep unshare shared_object.ep --user collaborator@example.com
ep push shared_object.ep
ep pull shared_object.ep
ep delete shared_object.ep --yes
```

Use `delete --yes` only when explicitly requested by the user.

The same commands can be reached under `ep objects`:

```bash
ep objects search --query "economics"
ep objects metadata shared_object.ep
ep objects push shared_object.ep
```

## Auth And Profiles

Check authentication before remote operations:

```bash
ep auth status
ep check
ep balance
ep credits
ep profile
ep settings
```

Login or configure credentials only when the user asks for it or when remote execution is clearly required:

```bash
ep auth login --api_key "$EXPECTED_PARROT_API_KEY"
```

Never print API keys. `ep info` and auth commands should redact credential values.

Profiles:

```bash
ep profiles list
ep profiles current
ep profiles show <name>
ep profiles set <name>
```

Use profiles when the task explicitly involves switching Expected Parrot environments or credentials.

## Humanize Workflow

Use `humanize` to create and manage human survey workflows.

```bash
ep humanize create --survey survey.ep --name "Customer interview"
ep humanize create --survey survey.ep --schema humanize.json
ep humanize create --jobs jobs.ep --scenario_method randomize
ep humanize list --page 1 --page_size 20
ep humanize status <human_survey_uuid>
ep humanize responses <human_survey_uuid> --output responses.ep
ep humanize qr <human_survey_uuid> --output qr.png
ep humanize preview --survey survey.ep --schema humanize.json
```

Schema and customization:

```bash
ep humanize schema validate --survey survey.ep --schema humanize.json
ep humanize schema patch <human_survey_uuid> --schema schema_patch.json
ep humanize css patch <human_survey_uuid> --file style.css
```

Respondents, deliveries, schedules, and callbacks:

```bash
ep humanize respondents <human_survey_uuid> --page 1 --page_size 50
ep humanize agent-list get <human_survey_uuid>
ep humanize agent-list patch <human_survey_uuid> --delivery_map delivery_map.json
ep humanize deliveries create <human_survey_uuid> --name "Initial invite"
ep humanize deliveries list <human_survey_uuid>
ep humanize deliveries tasks <human_survey_uuid> <delivery_uuid>
ep humanize deliveries wait <human_survey_uuid> <delivery_uuid> --timeout 60
ep humanize schedules create-one-time <human_survey_uuid> --name "Invite" --run_at 2026-07-05T12:00:00Z
ep humanize schedules create-cron <human_survey_uuid> --name "Weekly" --cron_expression "0 9 * * MON" --timezone America/New_York --max_jobs 4
ep humanize callbacks create <human_survey_uuid> --name "Transcript" --type human_survey_respondent.completed
ep humanize callbacks list <human_survey_uuid>
```

Rules:

- `humanize create` accepts either `--survey` or `--jobs`.
- Use `--survey` when starting from a survey package.
- Use `--jobs` when the package includes agents or scenarios.
- Jobs used for humanize must not include models.
- Jobs with scenarios require `--scenario_method`.

## Opening Objects

Use `ep open` for local HTML inspection. It may open a browser depending on flags and environment.

```bash
ep open survey.ep
ep open jobs.ep
ep open results.ep
```

In automation, prefer generated file paths or metadata from the JSON response over assuming a browser opened.

For non-browser package inspection:

```bash
ep inspect survey.ep
ep unpack survey.ep
ep unzip survey.ep
```

`ep unzip` is an alias for `ep unpack`.

## Pagination

Paginated commands include:

- `ep search`
- `ep jobs list`
- `ep humanize list`
- some `humanize` subcommands such as respondents and deliveries

Always pass explicit pagination in automation:

```bash
ep search --query "climate" --page 1 --page_size 50
ep jobs list --page 1 --page_size 50
ep humanize list --page 1 --page_size 50
```

Read returned pagination metadata such as `page`, `page_size`, `returned_count`, `total_pages`, and `total_count` when present.

## Error Handling

Common error classes:

- `USAGE_ERROR`: bad flags, missing input, conflicting options, or an invalid workflow.
- `INVALID_JSON`: malformed JSON input.
- `VALIDATION_ERROR`: JSON shape is parseable but not a valid EDSL object or question.
- `FILE_NOT_FOUND`: path does not exist.
- `AUTH_ERROR`: credentials are missing or invalid.
- `RUN_ERROR`: job construction or execution failed.
- `REMOTE_ERROR`: remote API operation failed.

Agent response pattern:

1. Parse stdout JSON.
2. If `status == "error"`, report `error.code`, `error.message`, and `error.suggestion`.
3. Do not retry blindly unless the suggestion is deterministic and safe.
4. For validation errors, run `ep validate` or `ep schema show`.
5. For remote errors, check `ep auth status`, `ep jobs status`, or retry only if the operation is idempotent.

## Recommended Agent Workflows

Run a prepared job and inspect answers:

```bash
ep validate --file jobs.ep
ep run jobs.ep --output results.ep
ep results columns --file results.ep
ep results select --file results.ep --column "answer.*" --limit 5
```

Submit a long remote job:

```bash
ep run jobs.ep --background
ep jobs status <job_uuid>
ep jobs results <job_uuid> --output results.ep
```

Create a quick smoke-test result:

```bash
ep run --question "Return the word ok." --model test --output smoke-results.ep
ep results select --file smoke-results.ep --column "answer.*"
```

Debug an input file:

```bash
ep validate --file input.json
ep schema show --class Jobs
ep inspect input.ep
```

## Do And Do Not

Do:

- Use `ep --help` and `ep <command> --help`.
- Use schemas before generating JSON.
- Save completed run results with `--output`.
- Use background mode for long remote jobs.
- Fetch remote results with `ep jobs results`.
- Repeat `--column` for multiple result columns.
- Keep destructive commands behind explicit user intent.

Do not:

- Expect `ep run` to print completed results inline.
- Parse progress text from stdout.
- Use `--background --output` without `--wait`.
- Guess serialized object shape.
- Print or expose API keys.
- Call `delete --yes` or `jobs cancel --yes` unless the user explicitly asked for deletion/cancellation.
