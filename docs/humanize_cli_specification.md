# Humanize CLI Specification

Status: draft for implementation planning.

This spec defines a first-pass `edsl humanize` CLI surface for creating and managing Expected Parrot human surveys from local EDSL assets. It intentionally focuses on the core workflow and leaves schedules, callbacks, deliveries, and Prolific for later command groups.

## Goals

- Provide a complete command-line workflow for humanizing a local Survey or Jobs package.
- Preserve the CLI contract used elsewhere in `edsl`: JSON envelopes, no prompts, no non-JSON stdout.
- Support `.ep` packages and JSON files consistently.
- Keep destructive or externally visible actions explicit.
- Avoid exposing raw Coop method names as the primary user interface.

## Non-Goals

- Full delivery/schedule/callback management in the first pass.
- Prolific study lifecycle management.
- Widget management.
- In-browser authentication or interactive setup.
- Arbitrary raw API passthrough.

## Command Group

```text
edsl humanize
```

Group discovery:

```json
{
  "status": "ok",
  "data": {
    "commands": [
      "list",
      "create",
      "status",
      "responses",
      "qr",
      "preview",
      "schema"
    ],
    "help": "Use 'edsl humanize <command> --help' for details."
  },
  "warnings": []
}
```

## Common Conventions

### Input Object Paths

Commands that accept a Survey or Jobs object should accept:

- `.ep` package paths
- package directories
- `.json`
- `.json.gz`

Survey-only commands must reject non-Survey objects with `UNSUPPORTED_OBJECT`.

Jobs-based creation may accept a Jobs object if it has:

- a Survey
- optional AgentList
- optional ScenarioList
- no models

This mirrors `Jobs.humanize()`, which rejects Jobs with models.

### Schema Files

Humanize schema inputs are JSON files:

```bash
--schema humanize_schema.json
```

If omitted, the command behaves as if no schema was supplied.

### Output Files

When commands write files, stdout still returns the normal JSON envelope with `saved_to` or `saved` metadata.

### Dates and Timezones

No schedule commands are included in this first pass. When schedules are later added, timezone-aware ISO strings should be required.

## Commands

### `edsl humanize list`

List human surveys owned by the authenticated user.

Backs onto:

```python
Coop.list_human_surveys(page, page_size, search_query, sort_ascending)
```

Flags:

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--query`, `-q` | string | null | Search by name or UUID |
| `--page` | int | 1 | Page number |
| `--page_size` | int | 10 | Results per page, max 100 |
| `--sort_ascending` | bool | false | Sort oldest first |

Output:

```json
{
  "status": "ok",
  "data": {
    "human_surveys": [
      {
        "uuid": "human-survey-uuid",
        "name": "Customer feedback",
        "visibility": "private",
        "created_ts": "2026-07-04T12:00:00Z",
        "n_responses": 12
      }
    ],
    "page": 1,
    "page_size": 10,
    "returned_count": 1,
    "total_pages": 1,
    "total_count": 1,
    "query": null,
    "sort_ascending": false
  },
  "warnings": []
}
```

Notes:

- The server returns a dict containing `human_surveys`, `current_page`, `page_size`, `total_pages`, and `total_count`.
- The CLI should normalize `current_page` to both `current_page` and `page` only if needed for consistency. Prefer echoing requested `page` and passing server `current_page` through when present.

### `edsl humanize create`

Create a human survey from a local Survey or Jobs object.

Backs onto:

```python
Coop.create_human_survey(...)
```

or existing object methods:

```python
Survey.humanize(...)
Jobs.humanize(...)
```

Preferred implementation: call `Coop.create_human_survey()` directly after loading the object, because the CLI needs to pass survey, agents, scenarios, schema, aliases, visibility, and scenario method explicitly.

Flags:

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--survey` | path | conditional | Local Survey `.ep`/JSON. Mutually exclusive with `--jobs` |
| `--jobs` | path | conditional | Local Jobs `.ep`/JSON. Mutually exclusive with `--survey` |
| `--name` | string | no | Human survey name; default `New survey` |
| `--schema` | path | no | Humanize schema JSON |
| `--scenario_list` | path | no | ScenarioList `.ep`/JSON; Survey input only |
| `--scenario_method` | enum | conditional | `randomize`, `loop`, `single_scenario`, or `ordered`; required if scenarios are supplied |
| `--agent_list` | path | no | AgentList `.ep`/JSON; Survey input only |
| `--survey_description` | string | no | Description for uploaded survey object |
| `--survey_alias` | string | no | Alias for uploaded survey object |
| `--survey_visibility` | enum | no | `private`, `public`, `unlisted`; default `private` |
| `--scenario_list_description` | string | no | Description for uploaded scenario list |
| `--scenario_list_alias` | string | no | Alias for uploaded scenario list |
| `--scenario_list_visibility` | enum | no | `private`, `public`, `unlisted`; default `private` |
| `--agent_list_description` | string | no | Description for uploaded agent list |
| `--agent_list_alias` | string | no | Alias for uploaded agent list |
| `--agent_list_visibility` | enum | no | `private`, `public`, `unlisted`; default `private` |
| `--delivery_map` | path | no | JSON delivery map. Validate using existing DeliveryMap model |

Examples:

```bash
edsl humanize create \
  --survey survey.ep \
  --name "Customer feedback" \
  --schema humanize_schema.json \
  --survey_alias customer-feedback \
  --survey_visibility private
```

```bash
edsl humanize create \
  --jobs study.ep \
  --name "Study validation" \
  --scenario_method randomize
```

Output:

```json
{
  "status": "ok",
  "data": {
    "name": "Customer feedback",
    "uuid": "human-survey-uuid",
    "admin_url": "https://www.expectedparrot.com/home/human-surveys/human-survey-uuid",
    "respondent_url": "https://www.expectedparrot.com/respond/human-surveys/human-survey-uuid",
    "n_responses": 0,
    "survey_uuid": "survey-uuid",
    "agent_list_uuid": null,
    "scenario_list_uuid": null
  },
  "warnings": []
}
```

Validation:

- Exactly one of `--survey` or `--jobs` is required.
- `--scenario_list` and `--scenario_method` must be supplied together.
- Jobs with models must fail with `VALIDATION_ERROR`.
- `--scenario_list` and `--agent_list` are invalid with `--jobs`; these should come from the Jobs object.
- Humanize schema is validated before creating anything remote.

### `edsl humanize status <human_survey_uuid>`

Fetch human survey metadata/status.

Backs onto:

```python
Coop.get_human_survey(human_survey_uuid)
```

Output:

```json
{
  "status": "ok",
  "data": {
    "name": "Customer feedback",
    "uuid": "human-survey-uuid",
    "admin_url": "https://www.expectedparrot.com/home/human-surveys/human-survey-uuid",
    "respondent_url": "https://www.expectedparrot.com/respond/human-surveys/human-survey-uuid",
    "n_responses": 12,
    "survey_uuid": "survey-uuid",
    "agent_list_uuid": null,
    "scenario_list_uuid": null
  },
  "warnings": []
}
```

### `edsl humanize responses <human_survey_uuid>`

Fetch human responses and optionally save them.

Backs onto:

```python
Coop.get_human_survey_responses(human_survey_uuid)
```

Flags:

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--output`, `-o` | path | null | Save as `.ep`, `.json`, or `.json.gz` |

Output without `--output`:

```json
{
  "status": "ok",
  "data": {
    "human_survey_uuid": "human-survey-uuid",
    "object_type": "Results",
    "result_count": 12
  },
  "warnings": []
}
```

Output with `--output`:

```json
{
  "status": "ok",
  "data": {
    "human_survey_uuid": "human-survey-uuid",
    "object_type": "Results",
    "result_count": 12,
    "saved": {
      "path": "responses.ep",
      "format": "ep",
      "object_type": "Results",
      "commit": "..."
    }
  },
  "warnings": []
}
```

Notes:

- `get_human_survey_responses()` may return a `Results` object or `ScenarioList` fallback.
- The save helper must support both. Existing `_save_results()` supports Results only; implementation should add `_save_edsl_object(obj, output_path)` or branch for ScenarioList.

### `edsl humanize qr <human_survey_uuid>`

Generate a QR code for the respondent URL.

Backs onto:

```python
Coop.get_human_survey_qr_code(human_survey_uuid)
```

Flags:

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--output`, `-o` | path | yes | PNG output path |

Output:

```json
{
  "status": "ok",
  "data": {
    "human_survey_uuid": "human-survey-uuid",
    "saved_to": "qr.png"
  },
  "warnings": []
}
```

Validation:

- `--output` is required.
- If the optional `qrcode` dependency is missing, return a structured `DEPENDENCY_ERROR` with installation suggestion.

### `edsl humanize preview`

Create/update an authenticated preview and return its URL.

Backs onto:

```python
Coop.get_survey_preview_url(survey, humanize_schema)
```

Flags:

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--survey` | path | yes | Survey `.ep`/JSON |
| `--schema` | path | no | Humanize schema JSON |

Output:

```json
{
  "status": "ok",
  "data": {
    "preview_url": "https://www.expectedparrot.com/home/human-surveys/preview/preview-uuid"
  },
  "warnings": []
}
```

### `edsl humanize schema validate`

Validate a humanize schema against a local Survey object without creating anything remote.

Backs onto local validator:

```python
validate_humanize_schema(survey, humanize_schema)
```

Flags:

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--survey` | path | yes | Survey `.ep`/JSON |
| `--schema` | path | yes | Humanize schema JSON |

Output:

```json
{
  "status": "ok",
  "data": {
    "valid": true
  },
  "warnings": []
}
```

Failure:

```json
{
  "status": "error",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Humanize schema references question 'q9', which is not in the survey."
  }
}
```

## Deferred Command Groups

These should not be part of the first implementation unless explicitly prioritized.

### `edsl humanize deliveries`

Potential commands:

```text
edsl humanize deliveries list <human_survey_uuid>
edsl humanize deliveries send <human_survey_uuid> --name ...
edsl humanize deliveries get <human_survey_uuid> <delivery_uuid>
edsl humanize deliveries tasks <human_survey_uuid> <delivery_uuid>
```

Backs onto `create_human_survey_delivery`, `list_human_survey_deliveries`, `get_human_survey_delivery`, `list_human_survey_delivery_tasks`.

### `edsl humanize schedules`

Potential commands:

```text
edsl humanize schedules list <human_survey_uuid>
edsl humanize schedules get <human_survey_uuid> <schedule_uuid>
edsl humanize schedules create-one-time ...
edsl humanize schedules create-cron ...
edsl humanize schedules activate ...
edsl humanize schedules deactivate ...
edsl humanize schedules delete ...
```

Requires careful datetime/timezone UX.

### `edsl humanize callbacks`

Potential commands:

```text
edsl humanize callbacks list <human_survey_uuid>
edsl humanize callbacks get <human_survey_uuid> <callback_uuid>
edsl humanize callbacks create ...
edsl humanize callbacks activate ...
edsl humanize callbacks deactivate ...
edsl humanize callbacks delete ...
```

Requires route schema UX.

### `edsl prolific`

Should be a separate top-level group, not nested under `humanize`, because it has its own lifecycle:

```text
edsl prolific filters
edsl prolific cost
edsl prolific create
edsl prolific update
edsl prolific publish
edsl prolific pause
edsl prolific resume
edsl prolific stop
edsl prolific submissions approve
edsl prolific submissions reject
```

## Implementation Plan

1. Add `humanize` and `humanize schema` Click groups in `edsl/__main__.py`.
2. Add object loader helpers:
   - `_load_survey_object(path)`
   - `_load_jobs_object(path)`
   - `_load_agent_list_object(path)`
   - `_load_scenario_list_object(path)`
   - `_read_json_or_gzip(path)`
3. Add `_save_edsl_object(obj, output_path)` supporting `.ep`, `.json`, `.json.gz`.
4. Implement `schema validate`, `preview`, `list`, `status`.
5. Implement `create` for Survey-only input.
6. Extend `create` for Jobs input and scenario/agent side inputs.
7. Implement `responses` and QR.
8. Add fake Coop tests for every command; no network.
9. Add one smoke flow:
   - validate schema
   - preview
   - create
   - status
   - responses save
   - qr save
10. Update `docs/cli_reference.md` with the final command list after implementation.

## Test Matrix

Required tests:

- `edsl humanize` lists subcommands.
- `schema validate` accepts valid schema.
- `schema validate` rejects schema referencing missing question.
- `preview` returns preview URL.
- `list` includes page metadata.
- `create --survey` calls `Coop.create_human_survey()` with expected args.
- `create --jobs` rejects Jobs with models.
- `create --jobs` maps Survey, AgentList, ScenarioList, and scenario method.
- `responses --output responses.ep` saves Results.
- `responses --output responses.json` saves JSON.
- `responses` handles ScenarioList fallback.
- `qr --output qr.png` calls QR save.
- Missing required paired `--scenario_list` / `--scenario_method` errors with `USAGE_ERROR`.
- Invalid object type errors with `UNSUPPORTED_OBJECT`.

## Open Questions

- Should `create` default `--name` from the survey package display name if omitted?
- Should `responses` print full response rows when `--output` is omitted, or only metadata? This spec chooses metadata to avoid huge stdout payloads.
- Should the CLI support `--schema-json` inline schema? This spec omits it to keep schemas file-based.
- Should delivery maps be included in first pass? This spec allows `--delivery_map` but does not expose delivery management commands.

