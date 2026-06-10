# object_store Module

A git-like content-addressable storage (CAS) system for versioning EDSL domain objects. Provides local persistence in the current working directory (`.edsl_objects/`), branching, commit history, diffing, and push/pull sync to a remote HTTP service.

## Architecture

```
ObjectStore              — Top-level API: save/load/list/delete/push/pull by UUID
  CASRepository          — Git-like CAS engine: blobs/trees/commits/refs/HEAD
    StorageBackend       — Protocol for key-value I/O (read/write/exists/delete/list_prefix)
      FileSystemBackend  — Local filesystem (default)
      HttpBackend        — Remote HTTP (buffered writes, push bundles)
      GCSBackend         — Google Cloud Storage (lazy-loaded, requires google-cloud-storage)
  MetadataIndex          — Protocol for object metadata + commit indexing + users/tokens
    SQLiteMetadataIndex  — SQLite at <root>/index.db (default, local)
    PostgreSQLMetadataIndex — PostgreSQL (lazy-loaded, requires psycopg2, used server-side)
  StoreDescriptor        — Python descriptor (edsl/base/store_accessor.py) exposing .store
  StreamingCASWriter     — Incremental writer for building CAS objects row-by-row
```

## File Inventory

| File | Class/Content | Purpose |
|------|---------------|---------|
| `__init__.py` | Package exports | Re-exports public API. GCSBackend and PostgreSQLMetadataIndex are lazy-loaded via helper functions to avoid mandatory dependencies. |
| `store.py` | `ObjectStore` | Main entry point. Manages UUIDs, delegates to CASRepository + MetadataIndex. Contains module-level sync helpers and the `_CLASS_REGISTRY`. |
| `cas_repository.py` | `CASRepository` | Pure infrastructure, no EDSL imports. Implements git-like storage: SHA-256 blobs, tree objects, commit chains, branch refs, HEAD. |
| `storage_backend.py` | `StorageBackend` | Runtime-checkable Protocol. Keys are relative paths like `"blobs/abc123.json"` or `"refs/main"`. Six methods: `read`, `write`, `exists`, `delete`, `list_prefix`, `delete_tree`. |
| `fs_backend.py` | `FileSystemBackend` | Local disk implementation. Uses `pathlib.Path` for all I/O. `delete_tree` uses `shutil.rmtree`. |
| `gcs_backend.py` | `GCSBackend` | Google Cloud Storage implementation. Keys stored under `{prefix}/` in a bucket. Requires `google-cloud-storage` (`pip install edsl[gcp]`). |
| `http_backend.py` | `HttpBackend` | Remote CAS service client. Buffers writes to `_pending_blobs/trees/commits` dicts; flushes as a single PushBundle POST when a ref is updated. Uses stdlib `urllib` only (no `requests` dependency). Key parsing via `_parse_cas_key()` / `_parse_ref_key()` regexes. |
| `metadata_index.py` | `MetadataIndex` | Runtime-checkable Protocol. Defines: object CRUD (`put/get/delete/list_all/search`), commit history (`put_commit/log`), user management (`create_user/get_user/list_users`), token auth (`create_token/validate_token/revoke_token`), ownership (`get_owner/set_owner`), alias resolution (`get_by_alias/resolve_alias`), metadata updates (`update_metadata`). |
| `sqlite_metadata_index.py` | `SQLiteMetadataIndex` | SQLite implementation. Tables: `objects`, `commits`, `users`, `tokens`. Thread-safe via `_ThreadSafeConnection` wrapper (threading.Lock). WAL journal mode. Supports context manager. Auto-migrates legacy `meta.json` files on first use. |
| `pg_metadata_index.py` | `PostgreSQLMetadataIndex` | PostgreSQL implementation. Same schema as SQLite. Uses `psycopg2.pool.ThreadedConnectionPool`. Identical MetadataIndex interface. Used by the remote CAS server. |
| `exceptions.py` | `AmbiguousUUIDError`, `StaleBranchError` | Both extend `BaseException`. `StaleBranchError` includes a user-friendly recovery message. |
| `store_info.py` | `StoreSaveInfo`, `StoreListInfo`, `StoreLogInfo`, `StoreDiffInfo` | Thin wrappers for operation results. Each subclasses a built-in (`dict`, `list`, `str`) so programmatic access works unchanged while adding `__repr__`, `_repr_html_`, and `_mime_` (Marimo) display methods. |
| `streaming_writer.py` | `StreamingCASWriter` | Incrementally builds a CAS object by appending JSONL rows. Each `append_result()` creates a new commit whose tree contains all rows so far. Caches row content in memory to avoid re-reading blobs. Used for streaming job results. |

## CAS Repository Layout (per object UUID)

```
<root>/<uuid>/
  HEAD                    — current branch name (e.g. "main\n")
  refs/<branch>           — branch tip commit hash
  blobs/<sha256>.json     — content-addressed data blobs (one per JSONL row)
  trees/<sha256>.json     — tree objects: {"blobs": ["<hash>", ...]}
  commits/<sha256>.json   — commit objects: {tree, parent, timestamp, message}
  current.jsonl           — convenience snapshot of HEAD content (reconstructed on each save)
```

All hashing uses SHA-256 hex digests on the string content.

## How Objects Are Stored (Save Flow)

1. `ObjectStore.save()` creates a `blob_writer` closure that stores FileStore blobs (large base64 data from ScenarioList) directly into the CAS backend's `blobs/` namespace for deduplication.
2. Domain object's `to_jsonl_rows(blob_writer=...)` is called, producing a list of JSONL row strings. Large blobs get replaced with `{"base64_string": "__cas_blob__", "__blob_hash__": "<hash>"}` sentinel values.
3. Each row string becomes its own content-addressed blob in `CASRepository.save()`.
4. A tree object records the ordered list of blob hashes.
5. A commit object records `{tree, parent, timestamp, message}`.
6. Branch ref is updated; HEAD points to branch name; `current.jsonl` is overwritten with the reconstructed content.
7. Metadata and commit are indexed in the `MetadataIndex` (SQLite or Postgres).

## How Objects Are Loaded

1. `ObjectStore.load()` resolves UUID (full, prefix, or alias) via `resolve_uuid()`.
2. `CASRepository.load()` reads HEAD -> branch ref -> commit -> tree -> blobs, reconstructing the JSONL string.
3. The object type is looked up in `_CLASS_REGISTRY` via the metadata index.
4. A `blob_reader` closure is created to resolve `__cas_blob__` sentinel values back to their original content.
5. `cls.from_jsonl(content, blob_reader=blob_reader)` deserializes the object.

## Storable Class Registry

Registered in `_CLASS_REGISTRY` in `store.py`:

| Type Name | Module Path |
|-----------|-------------|
| AgentList | `edsl.agents.agent_list` |
| Agent | `edsl.agents.agent` |
| Cache | `edsl.caching.cache` |
| ScenarioList | `edsl.scenarios.scenario_list` |
| Scenario | `edsl.scenarios.scenario` |
| ModelList | `edsl.language_models.model_list` |
| Survey | `edsl.surveys.survey` |
| Jobs | `edsl.jobs.jobs` |
| Results | `edsl.results.results` |
| QuestionBase | `edsl.questions.question_base` |
| Instruction | `edsl.instructions.instruction` |
| Study | `edsl.study.study` |

All entries are lazy-loaded via `importlib.import_module` to avoid circular imports. Use `register_storable(type_name, module_path, class_name)` to add new types at runtime. Each storable must implement `to_jsonl_rows(**kwargs) -> list[str]` and `classmethod from_jsonl(content, **kwargs)`.

## UUID Resolution

`ObjectStore.resolve_uuid(prefix)` accepts three forms:

1. **Full UUID** (36 chars, `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`) — returned as-is.
2. **Alias** — checked first via `MetadataIndex.resolve_alias()`.
3. **UUID prefix** (min 4 chars) — resolved via `MetadataIndex.resolve_prefix()`. Raises `AmbiguousUUIDError` if multiple matches.

## User-Facing API (via StoreDescriptor)

Domain objects get a `.store` descriptor (defined in `edsl/base/store_accessor.py`). The descriptor returns different accessor types depending on access:

### Instance-level (`InstanceStoreAccessor`)

```python
al = AgentList([Agent(traits={"age": 22})])

# Save (creates new UUID on first save, reuses on subsequent)
info = al.store.save(message="first version")   # returns StoreSaveInfo

# CAS tracking state (on the accessor, not the domain object)
al.store.uuid                    # UUID string
al.store.commit                  # last commit hash
al.store.current_branch          # current branch name

# Metadata (set as attributes, persisted on next save())
al.store.title = "My agents"
al.store.alias = "my-agents"
al.store.visibility = "public"
al.store.description = "Test agents"

# History and diffing
al.store.log()                   # commit history (returns ScenarioList)
al.store.diff()                  # HEAD~1 -> HEAD unified diff (StoreDiffInfo)
al.store.diff("HEAD~2")          # HEAD~2 -> HEAD
al.store.diff("abc123", "def456")  # explicit old -> new

# Branching
al.store.branch("experiment")    # create branch (does not switch)
al.store.checkout("experiment")  # switch HEAD
al.store.branches()              # list all branches

# Remote sync (defaults to EDSL_CAS_URL config and EXPECTED_PARROT_API_KEY env var)
al.store.push()                  # push to remote
al.store.pull()                  # pull from remote, updates in-memory object

# Metadata update without commit
al.store.update_metadata(title="New title")

# Reload from store
al2 = al.store.load()            # reload this object
al3 = al.store.load(uuid="...")  # load a different object
```

### Class-level (`ClassStoreAccessor`)

```python
AgentList.store.load(uuid)                 # load by UUID
AgentList.store.list()                     # list all stored AgentList objects (returns Dataset)
AgentList.store.delete(uuid)               # remove from store
AgentList.store.log(uuid)                  # commit history (returns StoreLogInfo)
AgentList.store.diff(uuid)                 # diff versions
AgentList.store.branches(uuid)             # list branches
AgentList.store.pull(uuid)                 # pull from remote and return loaded object
```

All methods accept `root=` to override the default current-working-directory location.

### Accessor State Management

- The `InstanceStoreAccessor` is cached on the domain object's `__dict__["_store_accessor"]` so CAS tracking state persists across accesses.
- On `save()`, `expected_tip=self.commit` is passed for compare-and-swap safety. If another save happened in between, `StaleBranchError` is raised.
- On `pull()`, the in-memory domain object's `__dict__` is updated with the pulled version's state, preserving the store accessor itself.
- Metadata attributes (`title`, `alias`, `visibility`, `description`) are consumed on `save()` and reset to None.

## Sync Protocol

`ObjectStore.sync(source, dest, branch=None)` copies CAS objects between any two `StorageBackend` implementations:

1. `_resolve_sync_branch()` — reads HEAD or explicit branch from source to get `(branch_name, tip_commit_hash)`.
2. Walks the commit chain backwards from tip. For each commit:
   - `_sync_commit()` copies the commit, its tree, all row blobs, and any file-blob references discovered by `_discover_blob_refs()` (scans for `__cas_blob__` sentinels in JSONL content).
   - Stops when a commit already exists on the destination (ancestor sharing).
3. `_update_dest_refs()` updates the ref, HEAD, and `current.jsonl` on the destination.

### Push path (local -> remote)

`ObjectStore.push()` creates an `HttpBackend` for the destination. Metadata is attached as `_pending_meta` on the backend so the remote can create the index entry. `sync()` skips per-object existence checks for HTTP destinations (`skip_exists=True`) since each `exists()` would be a slow HTTP round-trip; the push bundle protocol handles dedup server-side.

### Pull path (remote -> local)

`ObjectStore.pull()` creates an `HttpBackend` for the source. After `sync()`, it:
1. Fetches remote metadata and updates the local index.
2. Walks the pulled commit chain to index all commits in the local SQLite database (since `sync()` only copies CAS files, not index entries).

### HttpBackend Write Buffering

Writes are buffered in three dicts (`_pending_blobs`, `_pending_trees`, `_pending_commits`). When a `refs/<branch>` key is written, `_flush()` is triggered, which POSTs a `PushBundle` to `{prefix}/push/bundle`:

```json
{
  "objects": {
    "blobs/<hash>": "<content>",
    "trees/<hash>": "<json>",
    "commits/<hash>": "<json>"
  },
  "update_ref": {"branch": "main", "commit": "<hash>"},
  "meta": {"type": "AgentList", "description": "...", ...}
}
```

## StreamingCASWriter

For building CAS objects incrementally (used during job execution to stream results):

```python
writer = StreamingCASWriter(backend, branch="main")

# Write header/manifest rows (initial commit)
writer.write_preamble(["header_json", "manifest_json", "survey_json"])

# Append results one at a time (each creates a new commit)
writer.append_result('{"answer": "hello"}')

# Or in batches (single commit per batch)
writer.append_results_batch(['{"answer": "a"}', '{"answer": "b"}'])

writer.n_results  # count of result rows
writer.tip        # current commit hash
```

Every intermediate commit is valid and loadable. Row content is cached in memory (`_row_cache`) so `current.jsonl` can be rebuilt without re-reading blobs from the backend.

## Display Types (store_info.py)

| Class | Base | Used By | Features |
|-------|------|---------|----------|
| `StoreSaveInfo` | `dict` | `save()` | Keys: `status`, `uuid`, `branch`, `commit`, `message`. Has `_repr_html_` and `_mime_` (Marimo). |
| `StoreListInfo` | `list` | `ObjectStore.list()` | List of metadata dicts. Renders as table via `ScenarioList.to_dataset().to_markdown_table()`. |
| `StoreLogInfo` | `list` | `ClassStoreAccessor.log()` | List of commit dicts. Same rendering as StoreListInfo. |
| `StoreDiffInfo` | `str` | `diff()` | Unified diff text. `__repr__` adds ANSI colours (green/red/cyan). `_repr_html_` adds `<span>` colours. Has `.commit_a` and `.commit_b` attributes. |

Note: `InstanceStoreAccessor.log()` returns a `ScenarioList` directly instead of `StoreLogInfo`.

## Concurrency and Safety

- **Compare-and-swap**: `CASRepository.save()` accepts `expected_tip=` to reject saves if the branch has moved. Raises `StaleBranchError` with recovery instructions.
- **Thread safety**: `SQLiteMetadataIndex` wraps its connection in `_ThreadSafeConnection` (threading.Lock around every operation). `PostgreSQLMetadataIndex` uses `psycopg2.pool.ThreadedConnectionPool`.
- **WAL mode**: SQLite uses WAL journal mode for concurrent readers.
- **Content deduplication**: Identical row content produces the same SHA-256 hash, so only one blob is stored regardless of how many times the same content appears.
- **Immutable CAS objects**: Blobs, trees, and commits are never overwritten. Only refs (branch pointers) are mutable.

## SQLite Schema

Four tables in `index.db`:

```sql
objects(uuid PK, type, description, created, last_modified, owner, title, alias, visibility)
commits(hash, uuid, parent, tree, timestamp, message, branch, PK(uuid, hash), FK uuid->objects)
users(username PK, created)
tokens(token PK, username, created, FK username->users)
```

Indexes: `idx_objects_type`, `idx_objects_owner`, `idx_objects_owner_alias` (unique, partial WHERE alias IS NOT NULL), `idx_commits_uuid`, `idx_commits_branch`.

Both SQLite and PostgreSQL implementations share identical schemas. The PostgreSQL version uses `%s` placeholders and `psycopg2` instead of `?` placeholders and `sqlite3`.

## Legacy Migration

`SQLiteMetadataIndex.migrate_from_directory()` runs once on first access. If the `objects` table is empty, it scans `<root>/*/meta.json` files and imports them into SQLite. This handles migration from the pre-SQLite era when metadata lived in individual JSON files.

## Configuration and Defaults

- **Default root**: `Path.cwd() / ".edsl_objects"`
- **Default remote URL**: Read from `CONFIG.get("EDSL_CAS_URL")` (via `edsl.config`)
- **Auth token**: Read from `EXPECTED_PARROT_API_KEY` environment variable
- **Default branch**: `"main"`
- **Min UUID prefix length**: 4 characters

## Dependencies

- **Required**: `dotenv` (for env loading in store_accessor)
- **Optional**: `google-cloud-storage` for GCSBackend (`pip install edsl[gcp]`), `psycopg2` for PostgreSQLMetadataIndex
- **Stdlib only**: HttpBackend uses `urllib.request` (no `requests` dependency)
