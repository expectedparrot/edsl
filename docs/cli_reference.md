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
edsl docs
edsl skills
edsl collections
edsl playbooks
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

There is no user-facing `edsl coop` command. Expected Parrot-backed operations are exposed directly through task-oriented commands such as `search`, `push`, `pull`, `jobs`, `humanize`, `research-agent`, and `metadata`.

`edsl info` includes configuration diagnostics but redacts credential values such as API keys.

## Bundled Skills

EDSL ships version-matched implementation guidance that can be listed, searched,
displayed with its linked references, or copied to a harness directory:

```bash
ep skills list
ep skills list --routing --human
ep skills search survey
ep skills search loop_over --snippets --human
ep skills show edsl-surveys
ep skills show edsl-human-survey --reference references/humanize-schema.md
ep skills show <skill-name> --script scripts/<script-file>
ep skills show edsl-surveys --html
ep skills install --target ./skills
```

`ep skills show --html` uses Pandoc to render the skill and its linked local
references into one temporary page, then opens that page in the default browser.
`ep skills list --routing` returns each skill's name, description, tags, linked
reference paths, bundled script paths, and exact commands to fetch them. Skill
search also searches bundled script text. Use
`ep skills show <name> --script <path>` to retrieve script source through the
CLI. `ep skills install` copies the complete bundle; it does not run scripts.

## Playbooks

Playbooks are reusable EDSL `Prompt` objects stored on Expected Parrot. The
CLI caches catalog metadata locally for five minutes; `--refresh` forces a
fresh catalog fetch. Prompt bodies are fetched only when selected. A routing
view returns compact metadata and a ready-to-run fetch command:

```bash
ep playbooks list
ep playbooks list --routing
ep playbooks list --namespace ep --routing --refresh
ep playbooks search "customer interview" --namespace ep --page-size 5
ep playbooks search "interview-guide" --namespace johnjhorton
ep playbooks show alice/interview-guide
ep playbooks show alice/interview-guide --output - > interview-guide.md
ep playbooks show alice/interview-guide --output interview-guide.json
ep playbooks push interview-guide.md --alias interview-guide --description "Interview guide"
ep playbooks update alice/interview-guide interview-guide.md
```

`--namespace mine` searches playbooks owned by or shared with the current
account. `--namespace ep` searches the public EP catalog. A username such as
`--namespace johnjhorton` searches that owner's accessible playbooks.

Search checks aliases, owner names, and descriptions locally and marks the
matched field. JSON snapshots include the versioned Prompt and Coop metadata;
they can be reviewed locally, then passed to `push` to create or `update` to
replace an existing playbook's content. `push` creates by default; `--force`
explicitly overwrites an existing playbook with the same alias. `show --output
-` emits only raw prompt text for piping. Without `--output`, `show` returns
prompt text and metadata in the JSON envelope.

## Collections

Collections are local `.ep` packages containing ordered, typed UUID references
to objects stored on Expected Parrot. They do not embed member content or
change member permissions. Use `ep collections --help` and the subcommand help
for the installed options.

```bash
ep collections create --name "Study materials" --purpose "Survey and prompt references." --output study-materials.ep
ep collections add study-materials.ep "$SURVEY_UUID" --type survey
ep collections add study-materials.ep "$PROMPT_UUID" --type prompt
ep collections show study-materials.ep
ep collections metadata study-materials.ep
ep collections remove study-materials.ep "$PROMPT_UUID" --type prompt
ep push study-materials.ep --alias study-materials --description "Survey and prompt references for the study." --visibility private
ep clone "$COLLECTION_UUID" --path study-materials-copy.ep
ep pull study-materials-copy.ep
```

Use the UUIDs returned by `ep push` or shown by `ep metadata`; each reference
also needs the correct `--type`. Set `SURVEY_UUID` and `PROMPT_UUID` to those
UUIDs. `metadata` looks up current metadata for every member without fetching
object contents and requires access to each member.
`from-search` builds a collection from one result page, so check its pagination
metadata and warnings. Set `COLLECTION_UUID` to the UUID returned by `ep push`
before running the clone example. Collection visibility does not change member
visibility.
See [Collections](/en/latest/collections) for a complete guide and a search
example.

## Documentation Search

`ep docs` reads the currently published EDSL documentation from Mintlify. Public
search and Markdown retrieval do not require Mintlify credentials. The default
output is a JSON envelope; use `--human` to print Markdown or readable search
results directly to the terminal. Search returns a compact list of pages with
short excerpts; use `ep docs page` when you need the full content.

```bash
ep docs search "scenario list"
ep docs search "scenario list" --limit 3 --human
ep docs search "scenario list" --human
ep docs index --human
ep docs page scenarios --human
```

Use `ep docs index` to find page paths. For `ep docs page`, omit the `en/latest/`
prefix from the index path; the `.md` suffix is optional. Documentation is
fetched from the published site, so its content may be newer than the installed
EDSL version.

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

## Rehearse a saved job

A researcher assigns 16 employees to two versions of a survey. One version shows four activities, the other five. Each employee should report only a count. Check the saved schedule and look up an interview index for each arm.

```bash
ep jobs variants study.ep --group-by scenario.arm --unique-by agent.name --expect-interviews 16
```

Without `--group-by`, the command lists the assignment fields available throughout the schedule. Each group reports its assignment values, size and first interview index. Check the arm sizes against the design. Use `scenario.employee_id` when the respondent ID lives on the scenario. Repeat `--unique-by` for a composite key such as panelist and case. These checks cover the observed IDs. Confirm membership against the intended roster separately when required. Group on all fields that define the versions of interest.

For example, if the short arm starts at interview 3 and the long arm at interview 0, check both prompts and both boundaries.

```bash
ep jobs preview-prompt study.ep count --interview-index 3 --expect-comments false --forbid-text "explain"
ep jobs preview-prompt study.ep count --interview-index 0 --expect-comments false --forbid-text "explain"
ep jobs test-case study.ep --interview-index 3 --responses '{"count":4}' --expect '{"count":4}'
ep jobs test-case study.ep --interview-index 3 --responses '{"count":5}' --expect-rejection count
ep jobs test-case study.ep --interview-index 0 --responses '{"count":5}' --expect '{"count":5}'
```

Use the expected answer type for your question. String labels on a multiple-choice count return a string. When only whole totals are valid, also try `--responses '{"count":2.5}' --expect-rejection count`. Answer repair can accept a reply by converting it to an allowed value. The rejection check requires an answer-validation failure on the named question. An accepted answer, skipped question, or unrelated interview error fails the check. The comment flag checks the question setting. Read the rendered prompts for custom wording and inspect retained raw responses when disclosure matters. These commands exercise local EDSL model interviews.

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
edsl humanize responses <human_survey_uuid> --include-partial --output responses.ep
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
edsl humanize prolific list <human_survey_uuid>
edsl humanize prolific get <human_survey_uuid> <study_id>
edsl humanize prolific update <human_survey_uuid> <study_id> --config study-patch.json
edsl humanize prolific pause <human_survey_uuid> <study_id>
edsl humanize prolific resume <human_survey_uuid> <study_id>
edsl humanize prolific stop <human_survey_uuid> <study_id> --yes
edsl humanize prolific delete <human_survey_uuid> <draft_study_id> --yes
```

`edsl humanize create` accepts either `--survey` or `--jobs`. Use `--survey survey.ep` when starting from a survey package. Use `--jobs jobs.ep` when the package already includes agents or scenarios; jobs used for humanize must not include models. Jobs with scenarios require `--scenario_method`.

`edsl humanize list` is paginated and echoes `page`, `page_size`, and `returned_count`.

`edsl humanize assets` manages the image library a survey's logo is drawn from. Upload once and reference the asset uuid with `--logo-asset`, or pass `--logo-file` to `edsl humanize schema set` to upload and apply in one step. `edsl humanize schema create` accepts `--logo-asset` only, because it makes no server calls. Setting a new logo requires `--logo-alt` or `--logo-decorative`.

`edsl humanize schema create` and `edsl humanize schema set` take `--javascript QUESTION:HOOK=FILE` to attach a JavaScript file to a question's hook, for example `--javascript rating:question.ready=rating.js`; `question.ready` is the only hook today. `edsl humanize schema set` also takes `--clear-javascript QUESTION` to remove a question's JavaScript. Custom JavaScript is available on approved accounts only; check with `edsl humanize custom-js-access`. `edsl humanize events` returns the events a survey's scripts logged, oldest first, one batch at a time (`--limit`, at most 200); `--all` fetches every batch and requires `--output` (`.json` or `.jsonl`), so a whole log is written to a file rather than printed. Every result carries `next_cursor`: pass it as `--after` to get only newer events. Fetching only new events can occasionally miss one that was still being saved, so use it to check a survey while it collects, and download the full log for analysis once fielding has ended, at least an hour after the last response. `--count` returns how many events the survey has without fetching any.

Delivery, schedule, and callback commands accept optional `--routes` JSON files where supported. A route file may be a single route object or a list of route objects. Simple routes can also be created with helper flags such as `--owner-email-template owner_response_received` or `--respondent-email-template respondent_invitation`.

`edsl humanize prolific update --config` takes a JSON object containing only the fields to change. `stop` permanently ends a study and requires `--yes`; `delete` is limited to unpublished draft studies and also requires `--yes`.

## Research Agent sessions

`research-agent` commands use the configured Expected Parrot API key and operate on sessions the authenticated account can read. They require API-key authentication for the corresponding Coopr session routes.

```bash
edsl research-agent sessions --filter all --page 1 --page-size 50
edsl research-agent sessions --filter all --page 2 --page-size 50
edsl research-agent session <session-uuid>
edsl research-agent session <session-uuid> --section metadata
edsl research-agent session <session-uuid> --section shares
edsl research-agent session <session-uuid> --section files
edsl research-agent files <session-uuid>
edsl research-agent download <session-uuid> --file reports/summary.md --output summary.md
edsl research-agent download <session-uuid> --zip --output session.zip
edsl research-agent pull <session-uuid> --output ./session-copy
```

Session listing returns one page at a time (50 by default, up to 200). Its response includes has_next and next_page so callers can request another page. Use files to list a session's files, download to save one file or a ZIP, and pull to extract the complete session (including chat_history.md) into a new local directory. Pull destinations must not already exist; extracted files and directories are private to your user.

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
