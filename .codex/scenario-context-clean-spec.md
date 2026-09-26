# ScenarioContext: EDSL Working Context Spec

## Summary

Add a new Python class, `ScenarioContext`, for using a `ScenarioList` as durable working context for research agents and study-planning workflows.

Add a new CLI group:

```bash
ep context
```

The CLI should let a user or agent select one or more active context packages:

```bash
ep context use --path research_context.ep
```

Multiple context packages can be combined for reads:

```bash
ep context use --path personal_context.ep
ep context use --path team_context.ep --append
```

After that, read commands can omit the path:

```bash
ep context search --query "humanize survey back navigation"
ep context get --key preference.humanize.navigation
ep context pack --query "plan a human survey"
```

Write commands use a configured default write context, or an explicit `--path`:

```bash
ep context upsert --key preference.humanize.navigation --json @record.json
```

The active context pointer should be stored project-locally:

```text
.edsl/context.json
```

The context data itself should remain a normal git-backed `ScenarioList` `.ep` package:

```text
research_context.ep
```

## Motivation

A research agent that can write EDSL, plan studies, inspect prior work, and remember user preferences needs persistent context.

Examples:

- prior studies
- design notes
- user preferences
- reusable study patterns
- citations and source notes
- known constraints
- open questions
- artifact references
- preferred models or workflows

`ScenarioList` is a natural storage format because it is:

- EDSL-native
- a list of structured records
- serializable as an EDSL object
- already git-backed through `ScenarioList.git`
- inspectable and diffable
- directly usable in EDSL workflows

The missing layer is not storage. The missing layer is context semantics:

- keyed records
- upsert behavior
- BM25 search
- prompt packing
- active project context
- CLI commands designed for agents

## Core Design

Use three layers:

1. Generic `ScenarioList` methods for indexing, lookup, upsert, and BM25 search.
2. A new `ScenarioContext` Python class that wraps a `ScenarioList` and adds context semantics.
3. A new `ep context` CLI group that uses `ScenarioContext`.

Do not overload top-level `ep search`. Today `ep search` means remote/shared object search. Local working context should have a separate command surface.

Do not use `ep scenarios search research_context.scenarios`. There is no `.scenarios` path convention here. The context package should be a normal `.ep` object package, e.g. `research_context.ep`.

## V1 Decisions

- Class name: `ScenarioContext`.
- Active context config: `.edsl/context.json`.
- Read contexts: one or more ordered `active_context_paths`.
- Write context: one `default_write_context_path`.
- `pack` budget: character budget, exposed as `--char-budget`.
- `ep context upsert --message`: supported in v1 and passed to save when possible.
- `ScenarioList.upsert`: returns a new list by default; supports `in_place=True`.
- `ScenarioContext.search`: always returns scored records.
- `ScenarioList.search`: returns `ScenarioList` by default; scored records with `include_scores=True`.
- Codebook descriptions: not included in search text by default.
- Nested fields: explicit dotted paths are supported; deep indexing is not automatic.

## Python Class

Add:

```python
ScenarioContext
```

Suggested module:

```text
edsl/scenarios/scenario_context.py
```

Suggested export:

```python
from edsl import ScenarioContext
```

Prefer composition over subclassing:

```python
class ScenarioContext:
    def __init__(
        self,
        scenarios: ScenarioList | None = None,
        *,
        key_field: str = "key",
        default_search_fields: list[str] | None = None,
    ):
        self.scenarios = scenarios or ScenarioList()
```

Rationale:

- `ScenarioList` remains a generic data structure.
- `ScenarioContext` owns context-specific behavior.
- The CLI can delegate to `ScenarioContext`.
- Future context semantics do not clutter `ScenarioList`.

## Context Record Convention

Each context record is a `Scenario`.

Recommended fields:

```text
key
kind
title
summary
content
value
tags
source
uri
artifacts
created_at
updated_at
status
metadata
```

Only `key` is required for keyed operations.

`summary` is strongly recommended because it is the primary prompt-packing field.

Example:

```json
{
  "key": "preference.humanize.navigation",
  "kind": "user_preference",
  "summary": "User prefers Back settings in humanize_schema with question-level boundaries.",
  "value": {
    "survey_level": "back_button",
    "question_level": "allow_back_past"
  },
  "tags": ["humanize", "navigation", "survey_ui"],
  "source": "conversation",
  "created_at": "2026-07-17T10:00:00Z",
  "updated_at": "2026-07-17T10:00:00Z"
}
```

Example study note:

```json
{
  "key": "study.humanize-back-navigation-spec",
  "kind": "study_note",
  "title": "Back navigation for human surveys",
  "summary": "Spec for supporting Back button behavior through humanize_schema.",
  "uri": "https://github.com/expectedparrot/edsl/issues/2533",
  "artifacts": {
    "spec": ".codex/human-survey-back-navigation-spec.md"
  },
  "tags": ["humanize", "navigation", "spec"],
  "status": "proposed"
}
```

## ScenarioContext API

### Load

```python
ctx = ScenarioContext.load("research_context.ep")
```

Should load a `ScenarioList` from a normal EDSL object path/package and wrap it.

### Save

```python
ctx.save("research_context.ep")
ctx.save("research_context.ep", message="Update context")
```

If loaded from a path:

```python
ctx.save(message="Update context")
```

### Convert

```python
sl = ctx.to_scenario_list()
ctx = ScenarioContext.from_scenario_list(sl)
```

### Get

```python
record = ctx.get("preference.humanize.navigation")
record = ctx.get("missing.key", default=None)
```

### Add

Append a new context record:

```python
ctx.add(
    key="note.2026-07-17.back-navigation",
    kind="note",
    summary="Discussed Back button settings in humanize_schema.",
)
```

Default duplicate behavior should be conservative:

```python
duplicates="error"
```

### Upsert

Replace the record with the same key, or append if missing:

```python
ctx.upsert(
    key="preference.humanize.navigation",
    kind="user_preference",
    summary="User prefers Back settings in humanize_schema.",
    tags=["humanize", "navigation"],
)
```

Also support:

```python
ctx.upsert({"key": "...", "summary": "..."})
```

### Search

Use BM25 over selected fields:

```python
matches = ctx.search(
    "humanize back navigation",
    top_k=10,
)
```

Default fields:

```python
["key", "kind", "title", "summary", "content", "tags"]
```

Return ranked records:

```python
[
  {"score": 4.2, "scenario": Scenario(...)},
  {"score": 2.1, "scenario": Scenario(...)}
]
```

`ScenarioContext.search()` should always return scores. Context retrieval is ranking-sensitive, and agents benefit from seeing score metadata.

### Pack

Return compact prompt-ready context:

```python
prompt_context = ctx.pack(
    query="plan a study using humanize back navigation",
    top_k=8,
    char_budget=3000,
)
```

Example packed output:

```text
- [user_preference] preference.humanize.navigation: User prefers Back settings in humanize_schema with question-level boundaries.
- [study_note] study.humanize-back-navigation-spec: Spec filed for Back button behavior using humanize_schema.
```

V1 budget should be character-based. Token-aware packing can come later. The budget exists to bound how much retrieved context is rendered into a prompt; it does not affect the underlying search results.

## ScenarioList Methods

Add generic methods to `ScenarioList` where useful beyond context:

```python
scenarios.index_by("key")
scenarios.lookup("key", "preference.default_model")
scenarios.lookup_many("kind", "study")
scenarios.upsert("key", scenario)
scenarios.search("humanize back navigation", fields=["summary", "tags"], top_k=10)
scenarios.search("humanize back navigation", include_scores=True)
```

These should be generic collection affordances, not research-specific APIs.

`ScenarioContext` should use these methods internally where appropriate.

`ScenarioList.upsert()` should return a new `ScenarioList` by default, with an optional mutating mode:

```python
updated = scenarios.upsert("key", scenario)
scenarios.upsert("key", scenario, in_place=True)
```

`ScenarioList.search()` should return a `ScenarioList` by default. If `include_scores=True`, it should return scored records. This differs from `ScenarioContext.search()`, which should always return scored records.

## BM25 Search

Use the existing implementation:

```python
edsl.utilities.bm25.BM25Okapi
```

No new dependency is needed.

Tokenization should be simple but handle context keys:

- lowercase
- replace `.`, `_`, `-`, `/`, `:`, and `#` with spaces
- split on whitespace

This allows:

```text
preference.humanize.navigation
```

to match:

```text
humanize navigation
```

Do not serialize BM25 indexes in v1. Rebuild on search.

### Codebook

Do not include codebook descriptions in BM25 document text by default.

Rationale:

- codebook entries describe fields, not individual records
- repeated field descriptions can cause unrelated records to match
- search should focus on record content

Future versions can add:

```python
ctx.search(query, include_codebook=True)
```

or use codebook descriptions for display/explanation rather than document text.

### Nested Fields

Support dotted paths for explicitly requested fields:

```python
ctx.search(
    "github issue",
    fields=["summary", "artifacts.spec", "metadata.source"],
)
```

Do not deeply index all nested values by default. Default fields should remain shallow:

```python
["key", "kind", "title", "summary", "content", "tags"]
```

## Active Context Pointer

`ep context use` should write a project-local pointer:

```bash
ep context use --path research_context.ep
```

File:

```text
.edsl/context.json
```

Suggested contents:

```json
{
  "active_context_paths": ["research_context.ep"],
  "default_write_context_path": "research_context.ep"
}
```

Read path resolution for commands:

1. Explicit `--path`
2. Nearest `.edsl/context.json`, walking upward from current directory
3. Error

If multiple context paths are active, read commands should load all of them, concatenate their underlying `ScenarioList`s in order, and search/pack/get against the combined context.

Write path resolution for commands:

1. Explicit `--path`
2. `default_write_context_path` from the nearest `.edsl/context.json`
3. Error

Error:

```json
{
  "status": "error",
  "error": {
    "code": "CONTEXT_NOT_CONFIGURED",
    "message": "No active context path is configured.",
    "suggestion": "Run `ep context use --path research_context.ep` or pass `--path`."
  }
}
```

V1 should support only `.edsl/context.json`. A future version can add `.edsl/context.local.json` for personal overrides.

This design supports common workflows:

- individual context: `personal_context.ep`
- team context: `team_context.ep`
- project context: `project_context.ep`

Read commands can combine all active contexts. Write commands should update one target.

## CLI

Add:

```bash
ep context
```

All commands should follow EDSL CLI conventions:

- stdout is one JSON envelope
- stderr is diagnostics/logs
- no interactive prompts
- parse `status`

### `ep context use`

Set active context:

```bash
ep context use --path research_context.ep
```

Append another read context:

```bash
ep context use --path team_context.ep --append
```

Set the default write context explicitly:

```bash
ep context use --path personal_context.ep --write
```

Output:

```json
{
  "status": "ok",
  "data": {
    "active_context_paths": ["research_context.ep"],
    "default_write_context_path": "research_context.ep",
    "config_path": ".edsl/context.json"
  },
  "warnings": []
}
```

### `ep context current`

Show active context:

```bash
ep context current
```

### `ep context clear`

Clear active context:

```bash
ep context clear
```

### `ep context search`

Search active context:

```bash
ep context search --query "humanize survey back navigation consent randomization" \
  --field key \
  --field summary \
  --field content \
  --field tags \
  --top-k 10
```

Or with explicit path:

```bash
ep context search --path research_context.ep \
  --query "humanize survey back navigation consent randomization" \
  --top-k 10
```

Output:

```json
{
  "status": "ok",
  "data": {
    "context_path": "research_context.ep",
    "query": "humanize survey back navigation consent randomization",
    "matches": [
      {
        "score": 4.2,
        "scenario": {
          "key": "preference.humanize.navigation",
          "kind": "user_preference",
          "summary": "User prefers Back settings in humanize_schema with question-level boundaries."
        }
      }
    ]
  },
  "warnings": []
}
```

### `ep context get`

```bash
ep context get --key preference.humanize.navigation
```

### `ep context add`

```bash
ep context add --json @record.json
```

### `ep context upsert`

```bash
ep context upsert --key preference.humanize.navigation --json @record.json
```

If `--key` is omitted, read `key` from the JSON.

Optional:

```bash
--message "Update context"
```

passes through to `ScenarioContext.save(..., message=...)` when possible.

### `ep context pack`

```bash
ep context pack --query "plan a humanize back navigation study" --top-k 8 --char-budget 3000
```

`pack` searches for relevant records and renders them into a bounded prompt-ready text fragment. The character budget prevents an agent from dumping too much context into a prompt.

Output:

```json
{
  "status": "ok",
  "data": {
    "context_path": "research_context.ep",
    "query": "plan a humanize back navigation study",
    "prompt_context": "- [user_preference] preference.humanize.navigation: User prefers Back settings in humanize_schema with question-level boundaries."
  },
  "warnings": []
}
```

## Research Agent Workflow

Initial setup:

```bash
ep scenarios create --from-json initial_context.json --output research_context.ep
ep context use --path research_context.ep
```

Use personal and team context together:

```bash
ep context use --path personal_context.ep
ep context use --path team_context.ep --append
```

Before planning:

```bash
ep context pack --query "plan a conjoint pricing pilot" --top-k 8 --char-budget 3000
```

During work:

```bash
ep surveys create ...
ep jobs build ...
ep run jobs.ep --output results.ep
```

After learning something durable:

```bash
ep context upsert \
  --key preference.default_pilot_model \
  --json '{
    "key": "preference.default_pilot_model",
    "kind": "user_preference",
    "summary": "User prefers lower-cost models for pilot studies unless quality risk is high.",
    "tags": ["models", "cost", "pilot"]
  }' \
  --message "Update default pilot model preference"
```

After producing a study artifact:

```bash
ep context upsert \
  --key study.pricing-pilot-2026-07 \
  --json @study_context.json \
  --message "Add pricing pilot context"
```

## Tests

### ScenarioList

- `index_by`
- duplicate key behavior
- `lookup`
- `lookup_many`
- `upsert`
- BM25 `search`
- dotted key tokenization
- list/tag field search

### ScenarioContext

- create empty context
- load/save round trip
- `get`
- `add`
- duplicate add behavior
- `upsert`
- `search`
- `pack`
- default search fields
- explicit search fields
- path retention after load

### Context Pointer

- `ep context use --path ...` writes `.edsl/context.json`
- `ep context use --path ... --append` adds a read context
- `ep context use --path ... --write` sets the default write context
- `ep context current`
- `ep context clear`
- explicit `--path` overrides configured context
- upward search finds nearest `.edsl/context.json`
- missing config returns `CONTEXT_NOT_CONFIGURED`

### CLI

- `ep context search`
- `ep context get`
- `ep context add`
- `ep context upsert`
- `ep context pack`
- JSON envelope shape
- invalid JSON handling
- wrong object type at context path

## Implementation Phases

1. Add generic `ScenarioList` indexing/search/upsert methods.
2. Add `ScenarioContext`.
3. Add `.edsl/context.json` pointer helpers.
4. Add `ep context` CLI group.
5. Add docs/examples for research-agent workflows.

## Open Questions

- Should `.edsl/context.json` eventually support named contexts in addition to ordered active context paths?
- Should `.edsl/context.local.json` be added later for personal overrides?
- How should duplicate keys across multiple active context packages be displayed by `get`, `search`, and `pack`?
- Should `pack` eventually support model-aware token budgets?
