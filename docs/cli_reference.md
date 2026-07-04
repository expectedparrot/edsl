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
edsl humanize respondents <human_survey_uuid> --page 1 --page_size 50
edsl humanize agent-list get <human_survey_uuid>
edsl humanize agent-list patch <human_survey_uuid> --delivery_map delivery_map.json
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
