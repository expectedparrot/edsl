# object_store Module Overview

A git-like content-addressable storage (CAS) system for versioning EDSL domain objects (AgentList, ScenarioList, ModelList, Survey, Jobs). Provides local persistence via `platformdirs` (e.g. `~/Library/Application Support/edsl/objects/` on macOS), branching, commit history, and push/pull sync to a remote HTTP service.

## Architecture

```
ObjectStore          — Top-level API: save/load/list/delete/push/pull by UUID
  CASRepository      — Git-like CAS engine: blobs/trees/commits/refs/HEAD
    StorageBackend   — Protocol for key-value I/O (read/write/exists/delete/list_prefix)
      FileSystemBackend — Local filesystem implementation
      HttpBackend       — Remote HTTP implementation (buffered writes, push bundles)
  MetadataIndex      — Protocol for object metadata + commit indexing + users/tokens
    SQLiteMetadataIndex — SQLite implementation at <root>/index.db (supports context manager)
  StoreDescriptor    — Python descriptor (in edsl/base/store_accessor.py) that exposes
                        .store on domain objects for ergonomic access
```

## Key Files

| File | Purpose |
|------|---------|
| `store.py` | `ObjectStore` — main entry point. Manages UUIDs, delegates to CASRepository + MetadataIndex. Module-level helpers: `_discover_blob_refs()` for blob detection, `_resolve_sync_branch()` / `_sync_commit()` / `_update_dest_refs()` for sync. `register_storable()` for adding new types. |
| `cas_repository.py` | `CASRepository` — pure infrastructure, no EDSL imports. Implements git-like storage: SHA-256 content-addressed blobs, tree objects, commit chains, branch refs, HEAD. |
| `storage_backend.py` | `StorageBackend` — runtime-checkable Protocol. Keys are relative paths like `"blobs/abc123.json"` or `"refs/main"`. |
| `fs_backend.py` | `FileSystemBackend` — local disk implementation of StorageBackend. |
| `http_backend.py` | `HttpBackend` — remote CAS service client. Buffers writes and flushes as a PushBundle when a ref is updated. Uses key parsing via `_parse_cas_key()` / `_parse_ref_key()`. Has `get_metadata()` for fetching remote object metadata. |
| `metadata_index.py` | `MetadataIndex` — Protocol for object listing, commit history, user management, token auth. |
| `sqlite_metadata_index.py` | `SQLiteMetadataIndex` — SQLite implementation. Tables: `objects`, `commits`, `users`, `tokens`. Thread-safe. Supports context manager (`with`). Auto-migrates from legacy `meta.json` files. |
| `exceptions.py` | `StaleBranchError` — raised on compare-and-swap failure during save. |

## CAS Repository Layout (per object UUID)

```
<root>/<uuid>/
  HEAD                    — current branch name (e.g. "main\n")
  refs/<branch>           — branch tip commit hash
  blobs/<sha256>.json     — content-addressed data blobs
  trees/<sha256>.json     — tree objects ({"blobs": ["<hash>", ...]})
  commits/<sha256>.json   — commit objects (tree, parent, timestamp, message)
  current.jsonl           — convenience snapshot of HEAD content
```

## How Objects Are Stored

1. Domain object calls `to_jsonl(blob_writer=...)` to serialize to JSONL string
2. For ScenarioList with FileStore values, large base64 blobs are offloaded via `blob_writer` into separate CAS blobs (deduplication)
3. The JSONL string becomes a blob, wrapped in a tree, wrapped in a commit
4. Branch ref is updated; HEAD points to branch name

## User-Facing API (via StoreDescriptor)

Domain objects get a `.store` descriptor (defined in `edsl/base/store_accessor.py`):

```python
# Instance-level (InstanceStoreAccessor)
al = AgentList([Agent(traits={"age": 22})])
info = al.store.save(message="first version")   # returns {uuid, commit, branch, ...}
al.store.uuid                                     # tracks UUID
al.store.commit                                   # tracks last commit hash
al.store.current_branch                           # tracks current branch
al.store.log()                                    # commit history
al.store.branch("experiment")                     # create branch
al.store.checkout("experiment")                   # switch branch
al.store.push(remote_url="...")                   # sync to remote
al.store.pull(remote_url="...")                   # sync from remote
al.store.update_metadata(title="...", alias="...", visibility="public")

# Class-level (ClassStoreAccessor)
AgentList.store.load(uuid)                        # load by UUID
AgentList.store.list()                            # list all stored objects
AgentList.store.delete(uuid)                      # remove from store
AgentList.store.pull(uuid, remote_url="...")       # pull from remote
```

All methods accept `root=` to override the default platformdirs location.

## Sync Protocol

`ObjectStore.sync(source_backend, dest_backend)` copies CAS objects between any two StorageBackend implementations. Internally delegates to module-level helpers:
- `_resolve_sync_branch()` — resolve branch name and tip from source
- `_sync_commit()` — copy a single commit's blob/tree/commit + any file-blob refs
- `_discover_blob_refs()` — scan JSONL content for `__cas_blob__` sentinel values
- `_update_dest_refs()` — update ref, HEAD, and current.jsonl on destination
- Used by both `push()` (local -> HttpBackend) and `pull()` (HttpBackend -> local)

`HttpBackend` buffers writes and sends them as a single PushBundle POST when a ref is updated.

## Concurrency Safety

- `StaleBranchError` provides compare-and-swap: pass `expected_tip=` to reject saves if the branch tip moved
- `SQLiteMetadataIndex` uses a `_ThreadSafeConnection` wrapper with a threading lock
- SQLite uses WAL journal mode for concurrent readers

## Supported Object Types

Registered in `_CLASS_REGISTRY` in `store.py`: AgentList, ScenarioList, ModelList, Survey, Jobs. Use `register_storable()` to add new types at runtime. Each must implement `to_jsonl(**kwargs) -> str` and `classmethod from_jsonl(content, **kwargs)`.

## Tests

`tests/object_store/test_blob_offloading.py` — covers FileStore blob offloading, sidecar export, CAS round-trips, deduplication, and the StoreDescriptor integration.
