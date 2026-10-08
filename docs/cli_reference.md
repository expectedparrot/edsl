# EDSL CLI Reference

The `edsl` command is designed for agent and script use: stdout is a single JSON document, commands do not prompt, and errors use a consistent envelope.

## Envelope

Success:

```json
{
  "status": "ok",
  "data": {},
  "warnings": []
}
```

Error:

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

## Top-Level Commands

```text
edsl run
edsl validate
edsl models
edsl search
edsl clone
edsl push
edsl pull
edsl metadata
edsl update-metadata
edsl shared
edsl share
edsl unshare
edsl delete
edsl open
edsl results
edsl jobs
edsl humanize
edsl auth
edsl balance
edsl profile
edsl settings
edsl schema
edsl info
```

There is no user-facing `edsl coop` command. Expected Parrot-backed operations are exposed directly through task-oriented commands such as `search`, `push`, `pull`, `jobs`, `humanize`, and `metadata`.

`edsl info` includes configuration diagnostics but redacts credential values such as API keys.

## Local OpenAI-compatible Models

Create a portable model list for llama.cpp, Ollama, LM Studio, vLLM, SGLang, or another OpenAI-compatible server:

```bash
ep models create \
  --service openai_compatible \
  --model local-model \
  --base-url http://127.0.0.1:11434/v1 \
  --output local-models.ep
```

Run it without remote inference:

```bash
ep run \
  --question "Reply with ok." \
  --model_list local-models.ep \
  --local \
  --max-concurrency 4 \
  --api-timeout 300 \
  --output results.ep
```

Use `--api-key-env NAME` for an authenticated endpoint. Only the environment-variable name is serialized. See [Local OpenAI-compatible models](/en/latest/local_openai_compatible) for the full guide.

## Remote Object Workflow

```bash
edsl search --query "economics" --page_size 100
edsl clone <owner>/<alias> --path shared_object.ep
edsl metadata shared_object.ep
edsl update-metadata shared_object.ep --description "Updated" --visibility public
edsl shared shared_object.ep
edsl share shared_object.ep --user collaborator@example.com
edsl unshare shared_object.ep --user collaborator@example.com
edsl push shared_object.ep
edsl pull shared_object.ep
edsl delete shared_object.ep --yes
```

`delete` requires `--yes`.

Objects that have no `.ep` package format, such as prompts, are pushed from a `.json` or `.json.gz` file instead. Each push creates a new object:

```bash
edsl push prompt.json --alias research-brief --visibility private
edsl inspect prompt.json
```

## Remote Jobs

```bash
edsl run jobs.ep --background
edsl run jobs.ep --background --wait
edsl run jobs.ep --background --wait --poll_interval 10 --timeout 3600 --output results.ep
edsl jobs list --status running --page_size 100
edsl jobs status <job_uuid>
edsl jobs results <job_uuid> --output results.ep
edsl jobs errors <job_uuid> --output error.md
edsl jobs manifest <job_uuid>
edsl jobs page <job_uuid> --page 0 --page_size 100
edsl jobs cancel <job_uuid> --yes
edsl jobs cost jobs.ep --iterations 3
```

`jobs cancel` requires `--yes`.

`edsl run --background` submits the job to remote inference and returns immediately with `meta.remote_job.job_uuid`, progress URLs, and follow-up commands. Fetch completed results later with:

```bash
edsl jobs results <job_uuid> --output results.ep
```

Use `--wait` to submit the remote job, poll until it reaches a terminal status, and save completed results when `--output` is provided.

## Humanize

```bash
edsl humanize create --survey survey.ep --name "Customer interview"
edsl humanize create --survey survey.ep --schema humanize.json
edsl humanize create --jobs jobs.ep --scenario_method randomize
edsl humanize list --page 1 --page_size 20
edsl humanize status <human_survey_uuid>
edsl humanize responses <human_survey_uuid> --output responses.ep
edsl humanize qr <human_survey_uuid> --output qr.png
edsl humanize preview --survey survey.ep --schema humanize.json
edsl humanize schema validate --survey survey.ep --schema humanize.json
edsl humanize schema patch <human_survey_uuid> --schema schema_patch.json
edsl humanize css patch <human_survey_uuid> --file style.css
edsl humanize assets upload lab_logo.png
edsl humanize assets list --page 1 --page_size 20
edsl humanize assets get <asset_uuid> --output logo.png
edsl humanize assets delete <asset_uuid>
edsl humanize schema set <human_survey_uuid> --logo-asset <asset_uuid> --logo-alt "Acme Research logo"
edsl humanize schema set <human_survey_uuid> --logo-file lab_logo.png --logo-alt "Acme Research logo"
edsl humanize schema set <human_survey_uuid> --clear-logo
edsl humanize schema set <human_survey_uuid> --javascript rating:question.ready=rating.js
edsl humanize schema set <human_survey_uuid> --clear-javascript rating
edsl humanize custom-js-access
edsl humanize respondents <human_survey_uuid> --page 1 --page_size 50
edsl humanize events <human_survey_uuid> --limit 50
edsl humanize events <human_survey_uuid> --all --output events.jsonl
edsl humanize events <human_survey_uuid> --all --after <next_cursor> --output new.jsonl
edsl humanize events <human_survey_uuid> --count
edsl humanize agent-list get <human_survey_uuid>
edsl humanize agent-list patch <human_survey_uuid> --delivery_map delivery_map.json
edsl humanize agent-access get <human_survey_uuid>
edsl humanize agent-access patch <human_survey_uuid> --enabled --participation_mode autonomous --instructions "Keep free-text answers to one or two sentences, and use the comment box to flag any answer that's an estimate."
edsl humanize agent-access patch <human_survey_uuid> --question_instructions "improvements=Name at least one specific change, not a general comment." --clear_question job
edsl humanize agent-access patch <human_survey_uuid> --config agent_access.json
edsl humanize deliveries create <human_survey_uuid> --name "Initial invite"
edsl humanize deliveries create <human_survey_uuid> --name "Owner notice" --owner-email-template owner_response_received
edsl humanize deliveries list <human_survey_uuid>
edsl humanize deliveries tasks <human_survey_uuid> <delivery_uuid>
edsl humanize deliveries wait <human_survey_uuid> <delivery_uuid> --timeout 60
edsl humanize schedules create-one-time <human_survey_uuid> --name "Invite" --run_at 2026-07-05T12:00:00Z
edsl humanize schedules create-cron <human_survey_uuid> --name "Weekly" --cron_expression "0 9 * * MON" --timezone America/New_York --max_jobs 4
edsl humanize callbacks create <human_survey_uuid> --name "Transcript" --type human_survey_respondent.completed
edsl humanize callbacks list <human_survey_uuid>
```

`edsl humanize create` accepts either `--survey` or `--jobs`. Use `--survey survey.ep` when starting from a survey package. Use `--jobs jobs.ep` when the package already includes agents or scenarios; jobs used for humanize must not include models. Jobs with scenarios require `--scenario_method`.

`edsl humanize list` is paginated and echoes `page`, `page_size`, and `returned_count`.

`edsl humanize assets` manages the image library a survey's logo is drawn from. Upload once and reference the asset uuid with `--logo-asset`, or pass `--logo-file` to `edsl humanize schema set` to upload and apply in one step. `edsl humanize schema create` accepts `--logo-asset` only, because it makes no server calls. Setting a new logo requires `--logo-alt` or `--logo-decorative`.

`edsl humanize schema create` and `edsl humanize schema set` take `--javascript QUESTION:HOOK=FILE` to attach a JavaScript file to a question's hook, for example `--javascript rating:question.ready=rating.js`; `question.ready` is the only hook today. `edsl humanize schema set` also takes `--clear-javascript QUESTION` to remove a question's JavaScript. Custom JavaScript is available on approved accounts only; check with `edsl humanize custom-js-access`. `edsl humanize events` returns the events a survey's scripts logged, oldest first, one batch at a time (`--limit`, at most 200); `--all` fetches every batch and requires `--output` (`.json` or `.jsonl`), so a whole log is written to a file rather than printed. Every result carries `next_cursor`: pass it as `--after` to get only newer events. Fetching only new events can occasionally miss one that was still being saved, so use it to check a survey while it collects, and download the full log for analysis once fielding has ended, at least an hour after the last response. `--count` returns how many events the survey has without fetching any.

Delivery, schedule, and callback commands accept optional `--routes` JSON files where supported. A route file may be a single route object or a list of route objects. Simple routes can also be created with helper flags such as `--owner-email-template owner_response_received` or `--respondent-email-template respondent_invitation`.

## Results

```bash
edsl results columns --file results.ep
edsl results select --file results.ep --column "answer.*"
edsl results select --file results.json --column answer.q0 --limit 5
```

`edsl results columns` and `edsl results select` accept `.ep`, `.json`, and `.json.gz` Results files.

## Live Tests

```bash
EDSL_RUN_LIVE_CLI_TESTS=1 EDSL_LIVE_HUMAN_SURVEY_UUID=<uuid> pytest -q tests/test_cli_live.py
```

Live tests are read-only by default and use an existing human survey. The API does not currently support deleting human surveys through the client, so cleanup is not exposed as a CLI command.

## Pagination

`edsl search`, `edsl jobs list`, and `edsl humanize list` are paginated.

`edsl search` returns pagination metadata from the server when available:

```json
{
  "page": 1,
  "page_size": 10,
  "returned_count": 10,
  "current_page": 1,
  "total_pages": 7,
  "total_count": 63
}
```

`edsl jobs list` always echoes the requested page metadata:

```json
{
  "page": 1,
  "page_size": 10,
  "returned_count": 10
}
```

## Models

`edsl models` uses Expected Parrot's working model catalog and supports capability filters:

```bash
edsl models --service openai
edsl models --search gpt
edsl models --vision
edsl models --no-vision
edsl models --text
edsl models --no-text
```

The response includes `source`, `filters`, `count`, and model capability/pricing fields.

## Inline JSON

Both forms are accepted:

```bash
edsl validate --json '{"type":"free_text","question_text":"Hi"}'
edsl validate --json_data '{"type":"free_text","question_text":"Hi"}'
edsl run --json '{"type":"free_text","question_text":"Hi"}'
edsl run --json_data '{"type":"free_text","question_text":"Hi"}'
```
