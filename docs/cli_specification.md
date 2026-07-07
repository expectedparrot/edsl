# EDSL CLI Specification (v2)

An agent-friendly command-line interface for the EDSL package. Designed for AI coding agents: JSON-in/JSON-out, no interactive prompts, predictable structure.

---

## Design Principles

- **Structured output only**: stdout is always a single JSON document. stderr is for logs/diagnostics. Never mix them.
- **Stable output contracts**: output field names and shapes are a contract. Changing them is a breaking change. Nulls are preserved, never silently omitted. Arrays are deterministically ordered (alphabetical for schemas, insertion-order for results).
- **Execution-stateless**: commands do not depend on interactive session state. Any persistent state is explicit (stored auth credentials, environment variables, input files).
- **No interactivity**: no prompts, no spinners on stdout, no TTY assumptions.
- **Precise errors**: structured JSON errors with `code`, `message`, `suggestion` fields. Graduated exit codes.
- **Lazy imports**: only import edsl internals inside command handlers for fast startup.
- **Schema discoverability**: agents can introspect object schemas, question types, and required fields without reading docs.
- **File-based composition**: accept serialized EDSL objects as JSON files via explicit flags. All file arguments use flags, never positional args.
- **Consistent flag style**: all flags use `--flag_name` (underscores, matching Python/EDSL conventions).

---

## Response Envelope

All commands return a consistent top-level envelope:

**Success:**
```json
{
  "status": "ok",
  "data": { ... },
  "warnings": []
}
```

**Error:**
```json
{
  "status": "error",
  "error": {
    "code": "INVALID_MODEL",
    "message": "Model 'gpt-999' not found",
    "suggestion": "Use 'edsl models' to list available models"
  }
}
```

The `data` field contains the command-specific payload. The `warnings` array is always present on success (empty if none). The `error` object is present only on failure.

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Usage error (bad arguments, conflicting flags) |
| 3 | Resource not found |
| 4 | Authentication error (missing/invalid API key) |
| 5 | Validation error (input failed validation) |
| 6 | Remote service error (Coop/API unreachable or returned error) |

---

## Serialized Object Format

All serialized EDSL objects (Survey, AgentList, ScenarioList, ModelList, Results) use their native `to_dict()` output as the canonical serialized form. This is a public API contract.

Every serialized object includes versioning metadata:

```json
{
  "edsl_version": "1.0.7",
  "edsl_class_name": "Survey",
  ...
}
```

**Round-trip guarantee**: objects serialized with `to_dict()` and deserialized with `from_dict()` within the same major version are guaranteed to round-trip. Cross-version compatibility is best-effort.

---

## Commands

### `edsl run` — Run question(s) and get results

#### Input Normalization

All input modes compile to a **`Jobs` object** before execution. The `Jobs` class already has a standard serialized form via `Jobs.to_dict()`:

```json
{
  "survey": { ... },
  "agents": [ ... ],
  "models": [ ... ],
  "scenarios": [ ... ],
  "edsl_version": "1.0.7"
}
```

This is the canonical job JSON. It can be produced by `Jobs.to_dict()` in Python, pulled from Coop, or constructed by an agent and passed directly.

**Step 1: Determine base input source** (mutually exclusive, error if more than one provided):

| Priority | Source | Compiles to |
|----------|--------|-------------|
| 1 | `--jobs jobs.json` | Load serialized Jobs directly via `Jobs.from_dict()` — the most complete input mode |
| 2 | `--survey survey.json` | Load file as survey, other components empty |
| 3 | `--json '{...}'` | Parse JSON (see below for accepted shapes) |
| 4 | stdin (when not a TTY) | Parse JSON (same as --json) |
| 5 | `--question "text"` | Wrap as single-question survey |

When `--json` / stdin is used, the CLI auto-detects the shape:
- Has `"survey"` key → treated as serialized Jobs JSON, loaded via `Jobs.from_dict()`
- Has `"questions"` array → treated as a lightweight job spec (see below), compiled to Jobs
- Has `"type"` and `"question_text"` → single question shorthand, wrapped into a one-question survey

**Step 2: Apply component overrides.** CLI flags override corresponding components from the base input:

| Flag | Behavior |
|------|----------|
| `--agent_list agents.json` | **Replaces** agents from base input |
| `--scenario_list scenarios.json` | **Replaces** scenarios from base input |
| `--model_list models.json` | **Replaces** models from base input |
| `--model gpt-4o` | **Replaces** models with a single-model list |

`--model` and `--model_list` are mutually exclusive (exit code 2 if both provided).

When `--jobs` is used, component override flags are still allowed and replace the corresponding component in the loaded Jobs object.

**Step 3: Validate** the assembled Jobs object.

**Step 4: Execute** via `jobs.run()`.

#### Flags

**Input source (mutually exclusive):**
| Flag | Short | Description |
|------|-------|-------------|
| `--jobs` | | Path to serialized Jobs JSON (`Jobs.to_dict()` output) — the complete input |
| `--survey` | | Path to serialized Survey JSON |
| `--json` | | Inline JSON string (Jobs, question, or lightweight job spec) |
| `--question` | `-q` | Question text (creates free_text by default) |

**Component overrides (combinable with any input source):**
| Flag | Description |
|------|-------------|
| `--agent_list` | Path to serialized AgentList JSON (replaces agents) |
| `--scenario_list` | Path to serialized ScenarioList JSON (replaces scenarios) |
| `--model_list` | Path to serialized ModelList JSON (replaces models) |
| `--model` / `-m` | Model name — shortcut for single-model list (replaces models) |

**Quick-mode options** (only with `--question`):
| Flag | Short | Description |
|------|-------|-------------|
| `--type` | `-t` | Question type (default: `free_text`) |
| `--options` | | JSON array for MC/checkbox/etc. |
| `--name` | `-n` | Question name (auto-generated as `q0` if omitted) |

**Run options:**
| Flag | Description |
|------|-------------|
| `--progress` / `--no_progress` | Progress bar on stderr (default: no) |
| `--fresh` | Ignore cache, force new responses |
| `--save` | Also save full serialized Results to this file path |

#### Examples

```bash
# Simplest case
edsl run --question "What is 2+2?"

# Quick MC question with specific model
edsl run --question "Best color?" --type multiple_choice --options '["red","blue","green"]' -m gpt-4o

# Run a complete serialized Jobs object (produced by Jobs.to_dict() in Python)
edsl run --jobs job.json

# Run a Jobs object but override the model
edsl run --jobs job.json -m gpt-4o

# Compose from individual serialized components
edsl run --survey survey.json --agent_list agents.json --scenario_list scenarios.json --model_list models.json

# Survey file + model override (replaces models)
edsl run --survey survey.json -m gpt-4o

# Pipe serialized Jobs JSON from stdin
cat job.json | edsl run

# Single question JSON on stdin
echo '{"type":"multiple_choice","question_text":"Best?","question_options":["a","b"]}' | edsl run

# Save results for later querying
edsl run --survey survey.json --save results.json
```

#### Input JSON shapes (for `--json` / stdin)

**Shape 1: Serialized Jobs** (has `"survey"` key — loaded via `Jobs.from_dict()`):
```json
{
  "survey": { "questions": [...], "memory_plan": {...}, ... },
  "agents": [{ "traits": {...}, ... }],
  "models": [{ "model": "gpt-4o", "parameters": {...}, ... }],
  "scenarios": [{ "topic": "math" }],
  "edsl_version": "1.0.7"
}
```

**Shape 2: Lightweight job spec** (has `"questions"` array — compiled to Jobs):
```json
{
  "questions": [{"type": "free_text", "question_name": "q0", "question_text": "..."}],
  "agents": [{"traits": {"age": 30}}],
  "scenarios": [{"topic": "math"}],
  "models": ["gpt-4o"]
}
```

**Shape 3: Single question shorthand** (has `"type"` + `"question_text"` — auto-wrapped):
```json
{"type": "free_text", "question_text": "What is 2+2?"}
```

#### Output

```json
{
  "status": "ok",
  "data": {
    "results": [
      {
        "answer": {"q0": "4"},
        "agent": {"traits": {}},
        "scenario": {},
        "model": {"model": "gpt-4o", "service": "openai"}
      }
    ],
    "meta": {
      "input_mode": "question",
      "model_count": 1,
      "agent_count": 1,
      "scenario_count": 1,
      "result_count": 1,
      "cache_hits": 0,
      "cache_misses": 1
    }
  },
  "warnings": []
}
```

---

### `edsl models` — List available models

| Flag | Description |
|------|-------------|
| `--service` | Filter by service name |
| `--search` | Wildcard search pattern |
| `--text` / `--no-text` | Filter by text capability |
| `--vision` / `--no-vision` | Filter by image/vision capability |

**Output:**
```json
{
  "status": "ok",
  "data": {
    "source": "expected_parrot",
    "filters": {
      "service": "openai",
      "search": null,
      "text": null,
      "vision": true
    },
    "count": 1,
    "models": [
      {
        "model_name": "gpt-4o",
        "service_name": "openai",
        "configured": true,
        "works_with_text": true,
        "works_with_images": true,
        "usd_per_1M_input_tokens": 2.5,
        "usd_per_1M_output_tokens": 10.0
      }
    ]
  },
  "warnings": []
}
```

The command uses Expected Parrot's working model catalog. `configured` indicates whether API credentials for the model's service are available locally (via environment variable or stored key). Models are sorted alphabetically by service then model name.

```bash
edsl models --vision
edsl models --service openai --vision --search gpt
edsl models --no-vision
```

---

### `edsl auth` — Authentication management

**Note**: this is one of the few commands that mutates local state (stores credentials). All other commands are execution-stateless.

#### `edsl auth login`

| Flag | Description |
|------|-------------|
| `--api_key` | Provide key directly (skips browser flow) |

```bash
# Agent-friendly: set key directly, no browser needed
edsl auth login --api_key edsl_xxx
```

**Output:**
```json
{
  "status": "ok",
  "data": {"message": "API key stored successfully"},
  "warnings": []
}
```

Without `--api_key`, falls back to the browser-based login flow. Emits the login URL as JSON so an agent can present it to a human:
```json
{
  "status": "ok",
  "data": {
    "action": "awaiting_login",
    "login_url": "https://expectedparrot.com/login?edsl_auth_token=..."
  },
  "warnings": []
}
```

#### `edsl auth status`

```json
{
  "status": "ok",
  "data": {
    "authenticated": true,
    "username": "johnh",
    "api_key_source": "stored"
  },
  "warnings": []
}
```

Where `api_key_source` is one of: `"environment"`, `"stored"`, `"none"`.

---

### `edsl info` — Version, config, diagnostics

```json
{
  "status": "ok",
  "data": {
    "version": "1.0.7.dev1",
    "config": {"EDSL_DEFAULT_MODEL": "...", "EXPECTED_PARROT_URL": "..."},
    "api_key_configured": true
  },
  "warnings": []
}
```

---

### `edsl schema` — Introspect object schemas for construction

Agents use this to discover how to build EDSL objects without reading documentation.

#### `edsl schema question_types`

List all question types with their required and optional parameters. Sorted alphabetically by type.

```json
{
  "status": "ok",
  "data": {
    "question_types": [
      {
        "type": "free_text",
        "required": ["question_name", "question_text"],
        "optional": {"answering_instructions": "str", "question_presentation": "str"}
      },
      {
        "type": "multiple_choice",
        "required": ["question_name", "question_text", "question_options"],
        "optional": {"include_comment": "bool", "use_code": "bool"}
      }
    ]
  },
  "warnings": []
}
```

#### `edsl schema question --type <type>`

Detailed schema for one question type, including a working example.

```bash
edsl schema question --type multiple_choice
```

```json
{
  "status": "ok",
  "data": {
    "type": "multiple_choice",
    "required": ["question_name", "question_text", "question_options"],
    "optional": {"include_comment": "bool", "use_code": "bool", "permissive": "bool"},
    "example": {
      "type": "multiple_choice",
      "question_name": "color",
      "question_text": "What is your favorite color?",
      "question_options": ["Red", "Blue", "Green"]
    }
  },
  "warnings": []
}
```

#### `edsl schema survey`

Schema for the full job JSON accepted by `edsl run --json`.

#### `edsl schema agent` / `edsl schema scenario`

How to construct Agent and Scenario objects.

#### `edsl schema error`

Documents the error envelope and all known error codes.

---

### `edsl validate` — Validate JSON before running

Validate a question, survey, or job specification without executing it. Returns the normalized/canonical form on success.

| Flag | Description |
|------|-------------|
| `--file` | Path to JSON file to validate |
| `--json` | Inline JSON string to validate |
| (stdin) | Pipe JSON via stdin |
| `--type` | Force validation as a specific type (`question`, `survey`, `job`, `agent_list`, `scenario_list`) |

```bash
edsl validate --file survey.json
edsl validate --json '{"type": "free_text", "question_text": "Hi"}'
edsl validate --json '{"type": "free_text", "question_text": "Hi"}' --type question
cat survey.json | edsl validate
```

**Output on success:**
```json
{
  "status": "ok",
  "data": {
    "valid": true,
    "object_type": "question",
    "normalized": {
      "type": "free_text",
      "question_name": "q0",
      "question_text": "Hi"
    }
  },
  "warnings": [
    {
      "code": "AUTO_GENERATED_NAME",
      "message": "question_name was omitted and set to 'q0'"
    }
  ]
}
```

**Output on failure (exit code 5):**
```json
{
  "status": "error",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Input failed validation",
    "details": [
      {
        "path": "questions[0].question_options",
        "code": "REQUIRED_FIELD_MISSING",
        "message": "Field required when type is 'multiple_choice'",
        "suggestion": "Add a 'question_options' array with at least 2 items"
      }
    ]
  }
}
```

---

### `edsl results` — Query and extract data from a Results file

Load a serialized Results `.ep`, JSON, or JSON.gz file and run select/filter/order_by operations.

**V1 scope**: `columns` and `select` with `--filter` and `--order_by`. `--mutate` is deferred to a future version to avoid expression-language complexity.

#### `edsl results columns`

| Flag | Description |
|------|-------------|
| `--file` | Path to serialized Results `.ep`, JSON, or JSON.gz |

```json
{
  "status": "ok",
  "data": {
    "columns": [
      "answer.q0", "answer.q0_comment",
      "agent.age", "agent.occupation",
      "scenario.topic",
      "model.model", "model.service"
    ]
  },
  "warnings": []
}
```

#### `edsl results select`

| Flag | Short | Description |
|------|-------|-------------|
| `--file` | | Path to serialized Results `.ep`, JSON, or JSON.gz (required) |
| `--column` | | Column to select; repeat for multiple columns. Supports wildcards like `"answer.*"` |
| `--filter` | `-f` | Filter expression using EDSL's existing expression syntax |
| `--order_by` | | Sort by column |
| `--csv` | | Output as CSV instead of JSON |
| `--limit` | | Max rows to return |

**Column names**: selected columns are returned with their **full dotted names** to avoid collisions (e.g., both `agent.age` and `scenario.age` could exist).

```json
{
  "status": "ok",
  "data": {
    "data": [
      {"answer.q0": "Paris", "agent.age": 30},
      {"answer.q0": "London", "agent.age": 45}
    ]
  },
  "warnings": []
}
```

**Filter expressions** use EDSL's existing expression syntax (the same strings accepted by `Results.filter()` in Python). This is not arbitrary code evaluation — it uses EDSL's restricted expression parser.

#### Examples

```bash
# Select with filter
edsl results select --file results.ep --column "answer.*" --filter "agent.age > 30"

# Run then query
edsl run --survey survey.json --save results.json
edsl results select --file results.json --column answer.q0

# Full pipeline
edsl results columns --file results.ep
edsl results select --file results.ep --column answer.q0 --column agent.age --filter "model.model == 'gpt-4o'" --order_by agent.age
```

---

### `edsl search` — Search shared objects

Search for shared EDSL objects.

| Flag | Short | Description |
|------|-------|-------------|
| `--query` | `-q` | Search by description |
| `--type` | | Filter by object type (survey, agent_list, scenario_list, results, etc.) |
| `--visibility` | | public, private, unlisted |
| `--community` | | Search community objects (not just your own) |
| `--page` | | Page number (default: 1) |
| `--page_size` | | Results per page (default: 10, max: 100) |

```json
{
  "status": "ok",
  "data": {
    "objects": [
      {
        "uuid": "abc-123",
        "object_type": "survey",
        "alias": "user/my-survey",
        "description": "Onboarding feedback survey",
        "owner_username": "johnh",
        "visibility": "public"
      }
    ],
    "total": 42,
    "page": 1,
    "page_size": 20
  },
  "warnings": []
}
```

```bash
edsl search --type survey --query "onboarding" --community
edsl clone user/my-survey --path survey.ep
edsl pull survey.ep
edsl push survey.ep --description "Updated survey" --visibility public
```

`edsl search` is paginated. The response includes `page`, `page_size`, `returned_count`, and, when provided by the server, `current_page`, `total_pages`, and `total_count`.

### Remote Object Commands

These commands accept a UUID, full URL, `owner/alias`, or a local `.ep` package with stored remote metadata.

```bash
edsl metadata survey.ep
edsl update-metadata survey.ep --description "Updated description" --visibility public
edsl shared survey.ep
edsl share survey.ep --user collaborator@example.com
edsl unshare survey.ep --user collaborator@example.com
edsl delete survey.ep --yes
```

`edsl delete` requires `--yes` because it permanently deletes the remote object.

### Account Commands

```bash
edsl profile
edsl balance
edsl auth balance
edsl settings
```

### `edsl jobs` — Inspect and manage remote jobs

```bash
edsl run jobs.ep --background
edsl run jobs.ep --background --wait
edsl run jobs.ep --background --wait --poll_interval 10 --timeout 3600 --output results.ep
edsl run jobs.ep --background --remote_inference_description "Batch run"
edsl jobs list --status running --page_size 20
edsl jobs list --page 2 --page_size 100
edsl jobs status <job_uuid>
edsl jobs status --results <results_uuid>
edsl jobs results <job_uuid> --output results.ep
edsl jobs results --results <results_uuid> --output results.json
edsl jobs errors <job_uuid> --output error.md
edsl jobs manifest <job_uuid>
edsl jobs page <job_uuid> --page 0 --page_size 100
edsl jobs cancel <job_uuid> --yes
edsl jobs cost jobs.ep --iterations 3
```

`edsl jobs list` is paginated. The response includes `page`, `page_size`, and `returned_count` so callers know whether they are seeing only the first page.

`edsl jobs cost` accepts a local Jobs or Survey JSON/`.ep` object and returns the server-side remote run estimate.

`edsl run --background` submits a remote job and returns immediately. The JSON response includes `meta.remote_job.job_uuid`, progress URLs, and suggested follow-up commands. Since no completed Results object exists yet, combine it with `edsl jobs status`, `edsl jobs results`, or `edsl jobs errors`.

`edsl run --background --wait` keeps the CLI process open, polls `edsl jobs status` equivalent data until the job reaches a terminal status, and fetches completed results when possible. With `--output`, completed results are saved after polling succeeds.

### `edsl humanize` — Create and inspect human surveys

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

`edsl humanize create` accepts exactly one source: `--survey` or `--jobs`. A survey package such as `survey.ep` can be used directly with `--survey`. A Jobs package can supply the survey plus agents and scenarios, but must not include models; if scenarios are present, provide `--scenario_method`.

`edsl humanize list` is paginated and includes `page`, `page_size`, and `returned_count`.

Delivery, schedule, and callback commands accept optional `--routes` JSON files where supported. A route file may be a single route object or a list of route objects. Simple routes can also be created with helper flags such as `--owner-email-template owner_response_received` or `--respondent-email-template respondent_invitation`.

Live integration tests are opt-in:

```bash
EDSL_RUN_LIVE_CLI_TESTS=1 EDSL_LIVE_HUMAN_SURVEY_UUID=<uuid> pytest -q tests/test_cli_live.py
```

These tests use an existing human survey and avoid creating or deleting live objects by default. Human survey deletion is not exposed because the current API returns `405 Method Not Allowed` for that endpoint.

---

## Agent Workflow

A typical workflow for a coding agent using the CLI:

```bash
# 0. Authenticate (set API key directly - no browser needed)
edsl auth login --api_key edsl_xxx

# 1. Check what's available
edsl info
edsl models --service openai

# 2. Discover question types
edsl schema question_types

# 3. Get details on a specific type
edsl schema question --type multiple_choice

# 4. Validate before running (get back normalized form)
edsl validate --json '{"type":"free_text","question_text":"hi"}'

# 5. Run a quick question
edsl run --question "What do you think about AI?" -m gpt-4o

# 6. Run a full survey with composed files, save results
edsl run --survey survey.json --agent_list agents.json --scenario_list scenarios.json --save results.json

# 7. Query results
edsl results columns --file results.json
edsl results select --file results.json --column "answer.*" --column agent.age --filter "agent.age > 30"

# 8. Search and clone a shared object
edsl search --type survey --query "onboarding" --community
edsl clone user/my-survey --path survey.ep

# 9. Push a package
edsl push survey.ep --description "My survey" --visibility public

# 10. Inspect and manage remote metadata/jobs
edsl metadata survey.ep
edsl share survey.ep --user collaborator@example.com
edsl jobs list --status running
edsl jobs status <job_uuid>
```

---

## Design Decisions

### Output arrays are deterministically ordered
- `schema question_types`: alphabetical by type name
- `models`: alphabetical by service, then model name
- `results select`: insertion order (order of execution), unless `--order_by` is specified
- `search`: server-determined order (newest first by default)

### Null handling
Null values are preserved in output, never silently omitted. If a field has no value, it appears as `null`.

### Canonical serialized form
`to_dict()` is the canonical serialized form for all EDSL objects. This is treated as public API. The output includes `edsl_version` and `edsl_class_name` for version tracking.

### Expression language for filters
Filter expressions use EDSL's existing restricted expression parser (same as `Results.filter()` in Python). This is not `eval()` — it supports comparison operators, boolean logic, and column references only. No function calls, no arbitrary code.

### `edsl auth` mutates state
`auth login` and `auth logout` are explicitly marked as state-mutating commands. All other commands read from but do not write to local configuration.
