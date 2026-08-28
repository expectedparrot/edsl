# ScenarioContext Spec

## Summary

Add a new EDSL context abstraction backed by `ScenarioList`.

The proposed class, tentatively named `ScenarioContext`, represents a `ScenarioList` being used as durable working context for agents, research workflows, and study planning. It adds context-specific semantics such as keyed records, BM25 search, prompt packing, and save/load behavior while preserving `ScenarioList` as the underlying EDSL-native data format.

Add a new `ep context` CLI group for agent-friendly read/write/search workflows. The CLI should support an active project-local context pointer, set by:

```bash
ep context use --path research_context.ep
```

Subsequent commands can omit `--path`:

```bash
ep context search --query "humanize back navigation"
ep context get --key preference.humanize.navigation
ep context upsert --key preference.humanize.navigation --json @record.json
ep context pack --query "plan a human survey"
```

The active context pointer should live in a project-local file:

```text
.edsl/context.json
```

The context data itself remains a normal git-backed `ScenarioList` `.ep` package.

## Motivation

Research and study-planning agents benefit from persistent context:

- user preferences
- prior study designs
- past surveys and results
- notes and decisions
- reusable prompts and analysis patterns
- open questions and constraints
- citations and source references
- project-specific working memory

This context should be:

- readable and writable by agents
- inspectable by humans
- versionable
- portable
- searchable
- usable directly in EDSL workflows

`ScenarioList` is already a strong substrate:

- It is an EDSL-native list of structured records.
- It serializes to ordinary EDSL object formats.
- It has a git-backed `.ep` package format via `ScenarioList.git`.
- Each scenario can represent one context record.
- ScenarioLists can already be inspected, transformed, pushed, pulled, and used in jobs.

What is missing is a semantic layer for treating a `ScenarioList` as working context and a CLI surface designed for agent workflows.

## Design Principles

- Keep `ScenarioList` generic.
- Add broadly useful indexing/search primitives to `ScenarioList` where appropriate.
- Add context-specific behavior to a new `ScenarioContext` class.
- Use `ScenarioList` as the durable storage format.
- Use the existing git-backed `.ep` package behavior for versioning.
- Do not overload top-level `ep search`, which currently searches remote/shared objects.
- Use a dedicated `ep context` CLI group for context workflows.
- Keep the context pointer project-local, similar in spirit to Git's repository-local state.

## Current Implementation Context

Relevant code:

- `edsl/scenarios/scenario_list.py`
  - `ScenarioList` is the main collection type.
  - It already exposes `git = ScenarioListGitDescriptor()`.
- `edsl/scenarios/scenario_list_git.py`
  - Git-backed packages store a manifest and individual scenario JSON files.
  - Package validation checks manifest/scenario consistency.
- `edsl/utilities/bm25.py`
  - EDSL already includes a simple local `BM25Okapi` implementation.
- `edsl/questions/question_dropdown.py`
  - `QuestionDropdown` already uses local BM25 for option search.
- `edsl/cli_commands/scenarios.py`
  - Current CLI has `ep scenarios create` and `ep scenarios transform`.
- `edsl/cli_commands/objects.py`
  - Top-level `ep search` currently searches remote/shared Expected Parrot objects.
- `edsl/cli_commands/profiles.py`
  - Project-local `.edsl/profiles` and `.env` are used for Expected Parrot profile activation.

There is no existing `ep context` command group.

## Non-Goals

- Do not create a new database.
- Do not require vector search or embeddings for v1.
- Do not make context a separate storage format.
- Do not persist BM25 indexes into `.ep` packages in v1.
- Do not overload top-level `ep search`.
- Do not expose `ScenarioList.git` as ad hoc `ep scenarios git` commands unless a broader object-git CLI convention is added.
- Do not require every context record to conform to a rigid schema beyond what each operation needs.

## Data Model

`ScenarioContext` stores records as scenarios inside a `ScenarioList`.

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

`summary` is strongly recommended because it gives the agent a compact prompt-ready representation.

### Example Preference

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

### Example Study Note

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

### Example Open Question

```json
{
  "key": "question.randomization-boundaries",
  "kind": "open_question",
  "summary": "Are all humanize randomization boundaries represented as EDSL questions?",
  "tags": ["humanize", "randomization"],
  "status": "open"
}
```

## Storage And Versioning

The context package is a normal git-backed `ScenarioList` `.ep` package:

```text
research_context.ep
```

Internally, the package contains:

```text
manifest.json
codebook.json
scenarios/
  000001.json
  000002.json
  000003.json
```

Python workflow:

```python
from edsl import ScenarioContext

ctx = ScenarioContext()
ctx.upsert(
    key="preference.humanize.navigation",
    summary="User prefers Back settings in humanize_schema with question-level boundaries.",
    kind="user_preference",
    tags=["humanize", "navigation"],
)
ctx.save("research_context.ep", message="Add humanize navigation preference")
```

Versioning is handled by the underlying git-backed package machinery:

- context items are diffable JSON
- package state can be loaded by ref
- users and agents can inspect changes
- history for a key can be recovered from package history

The context layer should not invent a separate history system in v1.

## Active Context Pointer

The CLI should allow a project to choose an active context package:

```bash
ep context use --path research_context.ep
```

This writes:

```text
.edsl/context.json
```

Suggested file shape:

```json
{
  "active_context_path": "research_context.ep"
}
```

Path resolution:

1. Explicit `--path` on the command.
2. Nearest `.edsl/context.json`, walking upward from the current working directory.
3. Error with a suggestion to run `ep context use --path ...`.

Example error envelope:

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

Open question:

- Should v1 also support `.edsl/context.local.json` as a personal override?

Recommended v1:

- Support only `.edsl/context.json`.
- Document that teams can choose whether to commit it.

## Python API

Add a new class, tentatively:

```python
ScenarioContext
```

Recommended module:

```text
edsl/scenarios/scenario_context.py
```

Export from:

```python
from edsl import ScenarioContext
```

### Composition Over Subclassing

Prefer composition:

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

- `ScenarioList` remains the generic data structure.
- `ScenarioContext` owns context semantics.
- CLI can delegate to `ScenarioContext`.
- Future context-specific features do not clutter `ScenarioList`.

### Constructor

```python
ctx = ScenarioContext()
ctx = ScenarioContext(scenario_list)
```

### Loading

```python
ctx = ScenarioContext.load("research_context.ep")
```

This should accept any path that `load_any_object` / `ScenarioList.git.load` can already handle for `ScenarioList`.

### Saving

```python
ctx.save("research_context.ep")
ctx.save("research_context.ep", message="Update context")
```

If `ctx` was loaded from a path, `path` may be optional:

```python
ctx.save(message="Update context")
```

### Conversion

```python
sl = ctx.to_scenario_list()
ctx = ScenarioContext.from_scenario_list(sl)
```

### Keyed Lookup

```python
ctx.get("preference.humanize.navigation")
ctx.get("missing.key", default=None)
```

### Add

Append a new context record without replacing an existing key:

```python
ctx.add(
    key="note.2026-07-17.back-navigation",
    kind="note",
    summary="Discussed adding Back button settings to humanize_schema.",
)
```

If the key already exists, behavior should be configurable:

```python
ctx.add(..., duplicates="error")
ctx.add(..., duplicates="allow")
```

Recommended default:

```python
duplicates="error"
```

### Upsert

Replace the record with the same key or append if missing:

```python
ctx.upsert(
    key="preference.humanize.navigation",
    kind="user_preference",
    summary="User prefers Back settings in humanize_schema.",
    tags=["humanize", "navigation"],
)
```

Also allow an explicit record:

```python
ctx.upsert(record)
ctx.upsert({"key": "...", "summary": "..."})
```

### Search

```python
matches = ctx.search(
    "humanize back navigation",
    top_k=10,
)
```

Default search fields:

```python
["key", "kind", "title", "summary", "content", "tags"]
```

Allow override:

```python
ctx.search(
    "default model preference",
    fields=["key", "summary", "value", "tags"],
    top_k=5,
)
```

Return shape:

```python
[
    {"score": 4.2, "scenario": Scenario(...)},
    {"score": 2.1, "scenario": Scenario(...)},
]
```

This is better for context search than returning only a `ScenarioList`, because agents often need ranking information.

### Pack

Return compact prompt-ready context:

```python
prompt_context = ctx.pack(
    query="plan a study using humanize back navigation",
    top_k=8,
    budget=3000,
)
```

Example output:

```text
- [user_preference] preference.humanize.navigation: User prefers Back settings in humanize_schema with question-level boundaries.
- [study_note] study.humanize-back-navigation-spec: Spec filed for Back button behavior using humanize_schema.
```

Budget can be character-based in v1. Token-aware packing can come later.

### Current Path

If `ScenarioContext.load(path)` is used, preserve the path:

```python
ctx.path
```

This lets `ctx.save()` write back to the loaded package.

## Generic ScenarioList Methods

Add general-purpose collection affordances to `ScenarioList` where they are useful beyond context.

### `index_by`

```python
index = scenarios.index_by("key")
```

Options:

```python
scenarios.index_by("key", duplicates="error")
scenarios.index_by("key", duplicates="last")
scenarios.index_by("key", duplicates="list")
```

Recommended default:

```python
duplicates="error"
```

### `lookup`

```python
scenario = scenarios.lookup("key", "preference.default_model")
```

### `lookup_many`

```python
studies = scenarios.lookup_many("kind", "study")
```

Return:

```python
ScenarioList
```

### `upsert`

```python
updated = scenarios.upsert("key", scenario)
```

Open question:

- Should this mutate or return a new `ScenarioList`?

Recommendation:

- Follow existing `ScenarioList` transformation conventions.
- If unclear, return a new list by default and support `in_place=True`.

### BM25 Search

Generic `ScenarioList.search()` can use the same BM25 implementation as `ScenarioContext`, but should remain data-structure-oriented.

Possible API:

```python
matches = scenarios.search(
    "humanize back navigation",
    fields=["key", "summary", "content", "tags"],
    top_k=10,
    include_scores=True,
)
```

Return:

- `include_scores=False`: `ScenarioList`
- `include_scores=True`: list of `{score, scenario}` records

## BM25 Details

Use:

```python
edsl.utilities.bm25.BM25Okapi
```

Do not add a new dependency.

### Tokenization

V1 tokenization can be simple but should handle common context keys.

Recommended helper:

```python
_tokenize_for_bm25(text: str) -> list[str]
```

Suggested behavior:

- lowercase
- replace common separators with spaces:
  - `.`
  - `_`
  - `-`
  - `/`
  - `:`
  - `#`
- split on whitespace

This helps:

```text
preference.humanize.navigation
```

match:

```text
humanize navigation
```

### Indexing

Do not serialize search indexes.

V1 can rebuild the BM25 index on each search. Context lists are expected to be modest in size.

Later:

- cache by fields and content fingerprint
- support semantic/vector search

## CLI Design

Add a new top-level group:

```bash
ep context
```

This group uses `ScenarioContext`.

### `ep context use`

Set the active context package for the current project:

```bash
ep context use --path research_context.ep
```

Output:

```json
{
  "status": "ok",
  "data": {
    "active_context_path": "research_context.ep",
    "config_path": ".edsl/context.json"
  },
  "warnings": []
}
```

Options:

```bash
--path PATH
--config PATH   # optional override for .edsl/context.json
```

### `ep context current`

Show the active context:

```bash
ep context current
```

Output:

```json
{
  "status": "ok",
  "data": {
    "active_context_path": "research_context.ep",
    "config_path": ".edsl/context.json",
    "exists": true
  },
  "warnings": []
}
```

### `ep context clear`

Remove the active context pointer:

```bash
ep context clear
```

This should remove or update `.edsl/context.json`.

### `ep context search`

Search active context:

```bash
ep context search --query "humanize back navigation" --top-k 10
```

Override path:

```bash
ep context search --path other_context.ep --query "humanize back navigation"
```

Output:

```json
{
  "status": "ok",
  "data": {
    "context_path": "research_context.ep",
    "query": "humanize back navigation",
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

Options:

```bash
--query TEXT
--field FIELD      # repeatable
--top-k N
--path PATH
```

### `ep context get`

Get a record by key:

```bash
ep context get --key preference.humanize.navigation
```

Options:

```bash
--key KEY
--path PATH
```

### `ep context add`

Append a record:

```bash
ep context add --json @record.json
```

Or inline:

```bash
ep context add --json '{"key":"note.foo","summary":"..."}'
```

Options:

```bash
--json JSON_OR_PATH
--path PATH
--message MESSAGE
```

### `ep context upsert`

Add or replace by key:

```bash
ep context upsert \
  --key preference.humanize.navigation \
  --json @record.json
```

If `--key` is omitted, read `key` from the JSON record:

```bash
ep context upsert --json @record.json
```

Options:

```bash
--key KEY
--json JSON_OR_PATH
--path PATH
--message MESSAGE
```

`--message` should pass through to `ScenarioContext.save(..., message=...)` if the underlying save path supports git commit messages.

### `ep context pack`

Return prompt-ready context:

```bash
ep context pack --query "plan a study using humanize back navigation" --top-k 8
```

Options:

```bash
--query TEXT
--top-k N
--budget N
--path PATH
```

Output:

```json
{
  "status": "ok",
  "data": {
    "context_path": "research_context.ep",
    "query": "plan a study using humanize back navigation",
    "prompt_context": "- [user_preference] preference.humanize.navigation: User prefers Back settings in humanize_schema with question-level boundaries."
  },
  "warnings": []
}
```

## Research Agent Workflow

### Initial Setup

Create or choose a context package:

```bash
ep scenarios create --from-json initial_context.json --output research_context.ep
ep context use --path research_context.ep
```

### Before Planning

Retrieve relevant context:

```bash
ep context search --query "conjoint pricing pilot user preferences" --top-k 8
```

Or pack directly for a prompt:

```bash
ep context pack --query "plan a conjoint pricing pilot" --top-k 8 --budget 3000
```

### During Work

The agent can use ordinary EDSL commands:

```bash
ep surveys create ...
ep jobs build ...
ep run jobs.ep --output results.ep
```

### After Learning Something Durable

Write a preference:

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

Write a study artifact record:

```bash
ep context upsert \
  --key study.pricing-pilot-2026-07 \
  --json @study_context.json \
  --message "Add pricing pilot context"
```

## CLI JSON Conventions

All `ep context` commands should follow EDSL CLI conventions:

- stdout is a single JSON envelope
- diagnostics go to stderr
- no interactive prompts
- parse stdout JSON and inspect `status`

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
    "code": "CONTEXT_NOT_CONFIGURED",
    "message": "No active context path is configured.",
    "suggestion": "Run `ep context use --path research_context.ep` or pass `--path`."
  }
}
```

## Testing Plan

### ScenarioList Unit Tests

Add tests for:

- `index_by`
- duplicate behavior
- `lookup`
- `lookup_many`
- `upsert`
- `search`
- BM25 matching over tags/list fields
- BM25 matching dotted keys

### ScenarioContext Unit Tests

Add tests for:

- empty context creation
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

### Context Pointer Tests

Add tests for:

- `ep context use --path ...` writes `.edsl/context.json`
- `ep context current` reports configured context
- `ep context clear` removes active context
- command resolution uses explicit `--path` over configured path
- upward search finds nearest `.edsl/context.json`
- missing context returns `CONTEXT_NOT_CONFIGURED`

### CLI Tests

Add tests for:

- `ep context search`
- `ep context get`
- `ep context add`
- `ep context upsert`
- `ep context pack`
- JSON envelope shape
- invalid JSON handling
- wrong object type at context path

## Implementation Phases

### Phase 1: Generic ScenarioList Methods

- Add `index_by`.
- Add `lookup`.
- Add `lookup_many`.
- Add `upsert`.
- Add BM25 `search`.
- Add unit tests.

### Phase 2: ScenarioContext Python Class

- Add `ScenarioContext`.
- Add load/save.
- Add get/add/upsert/search/pack.
- Export from `edsl`.
- Add unit tests.

### Phase 3: Active Context Pointer

- Add helper for `.edsl/context.json`.
- Add upward directory search.
- Add tests.

### Phase 4: `ep context` CLI

- Add new CLI group.
- Add `use`, `current`, `clear`, `search`, `get`, `add`, `upsert`, `pack`.
- Add CLI tests.

### Phase 5: Documentation And Examples

- Document recommended context record fields.
- Add research-agent workflow examples.
- Add examples showing `.ep` package versioning.

## Open Questions

- Should the class be named `ScenarioContext`, `Context`, or `ResearchContext`?
- Should `ScenarioContext` use composition or subclass `ScenarioList`? This spec recommends composition.
- Should `.edsl/context.local.json` be supported in v1?
- Should `.edsl/context.json` store only one active path or multiple named contexts?
- Should `pack` use character budget or token budget in v1?
- Should `ep context upsert --message` be supported immediately?
- Should `ScenarioList.upsert` mutate or return a new list?
- Should `ScenarioContext.search` always return scores?
- Should codebook descriptions be included in search text?
- Should nested fields be searchable via dotted paths?

