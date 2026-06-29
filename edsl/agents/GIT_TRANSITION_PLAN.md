# AgentList Git Storage Transition Plan

## Goal

Migrate AgentList remote persistence from the current Coop JSON blob model to
Git-backed `.agent_list.ep` packages without breaking existing callers,
downstream consumers, or legacy object URLs.

Today, `agent_list.push()` sends a serialized JSON blob to Coop, which
overwrites a remote GCS entry for that object. The new direction is to make a
Git package the canonical versioned representation while keeping the legacy JSON
blob available as a compatibility view during and after migration.

## Target Model

The public API should remain stable for normal users:

```python
agent_list.push()
agent_list.pull()
AgentList.pull(...)
```

Git should become the backing storage engine, not a required user concept.
Power users can use:

```python
agent_list.git.save(...)
agent_list.git.branch(...)
agent_list.git.checkout(...)
agent_list.git.push(...)
```

but existing Coop workflows should continue to work.

The eventual canonical remote object should be a Git-backed
`.agent_list.ep` repository. The legacy JSON blob should become either:

- a generated snapshot of Git `HEAD`, or
- a compatibility endpoint backed by the latest Git commit.

## Recommended Remote Shape

Prefer one Git repo per AgentList object:

```text
<remote-root>/agent-lists/<uuid>.agent_list.ep.git
```

This maps cleanly to the current object/UUID model and avoids repo-wide
branching and conflict issues that would come from storing many AgentLists in a
single monorepo.

Each Coop object should store metadata linking legacy and Git representations:

```json
{
  "uuid": "...",
  "edsl_class_name": "AgentList",
  "storage_version": 2,
  "canonical_storage": "git_package",
  "git_remote_url": "...",
  "git_commit": "...",
  "legacy_json_snapshot": "..."
}
```

## Migration Phases

### Phase 1: Dual Write

Keep legacy JSON canonical.

When `agent_list.push()` runs:

1. Write the legacy JSON blob exactly as today.
2. Also save and push the `.agent_list.ep` Git package.
3. Store metadata linking the Coop object UUID, Git remote URL, current Git
   commit, and migration status.

Reads still default to legacy JSON. This makes the new representation observable
without changing existing behavior.

### Phase 2: Read-Through Validation

When `AgentList.pull()` reads legacy JSON, optionally check whether a Git
package exists for the same object.

If it exists:

1. Load the legacy JSON representation.
2. Load the Git package representation.
3. Compare semantic equality.
4. Log or report mismatches internally.
5. Return the legacy JSON result.

This proves serialization fidelity before Git becomes a read source.

### Phase 3: Git-Primary Reads With JSON Fallback

For explicitly migrated objects:

1. Load from the Git package `HEAD`.
2. If Git load fails, fall back to the legacy JSON blob.
3. Log fallback events.

At this stage, Git is canonical for migrated objects, but existing callers still
receive an `AgentList` through the same API.

### Phase 4: Generated Legacy JSON Snapshot

Stop treating the legacy JSON blob as independently writable.

After each successful Git push:

1. Load Git `HEAD`.
2. Generate the legacy JSON blob from that state.
3. Update the existing JSON endpoint/blob.

The legacy JSON object remains available for old consumers, but it is now a
derived compatibility artifact.

### Phase 5: Reject Legacy-Only Writes

For migrated objects, reject or warn on any write path that updates only the
legacy JSON blob.

All writes should flow through the Git package representation so history,
branches, and commit metadata remain coherent.

## API Compatibility

Keep existing APIs:

```python
agent_list.push()
AgentList.pull(uuid)
```

Add temporary controls for migration and debugging:

```python
agent_list.push(storage="legacy")
agent_list.push(storage="dual")
agent_list.push(storage="git")

AgentList.pull(uuid, storage="auto")
AgentList.pull(uuid, storage="legacy")
AgentList.pull(uuid, storage="git")
```

For migrated objects, support Git refs:

```python
AgentList.pull(uuid, ref="main")
AgentList.pull(uuid, ref="HEAD~2")
AgentList.pull(uuid, ref="<commit>")
```

The default should eventually become:

```python
storage="auto"
```

where migrated objects read from Git and non-migrated objects read from legacy
JSON.

## Coop Integration

Coop does not need to expose every Git operation immediately. Start with a thin
bridge:

```python
agent_list.push()
```

should:

1. Ensure the object has a Coop UUID.
2. Ensure a remote Git package repo exists.
3. Save the local Git package.
4. Push the Git package.
5. Generate/update the legacy JSON snapshot.
6. Update Coop metadata with the Git commit hash.

`AgentList.pull(uuid)` should:

1. Fetch Coop metadata.
2. Decide whether the object is legacy, dual-written, or Git-canonical.
3. Load from the selected representation.
4. Preserve fallback behavior during migration.

## Rollback Strategy

Every migrated object should keep its last known-good legacy JSON snapshot.

If Git-backed reads or writes fail in production:

1. Flip reads back to legacy JSON.
2. Disable Git writes or keep them diagnostic-only.
3. Preserve Git package repos for debugging.

Do not delete legacy JSON blobs until all consumers have moved off direct JSON
dependencies.

## Risks

- Mapping existing Coop UUIDs to Git repos.
- Keeping generated legacy JSON snapshots semantically identical.
- Auth and permissions for Git remotes.
- Server-side Git support if GCS is currently only blob overwrite.
- Divergent histories when multiple clients push concurrently.
- Performance and operational overhead for many small Git repos.
- Merge/conflict behavior.
- External consumers depending on raw legacy JSON URLs.

## Initial Implementation Checklist

1. Add feature flag for dual-write on `AgentList.push()`.
2. Add Coop metadata fields for Git package URL, commit, and storage version.
3. Implement Git package creation/push behind existing `push()`.
4. Generate legacy JSON snapshot from Git `HEAD`.
5. Add semantic compare between legacy JSON and Git package loads.
6. Add telemetry/logging for mismatch and fallback events.
7. Enable Git-primary reads for explicitly migrated objects.
8. Make Git package canonical for newly created AgentLists.
9. Keep legacy JSON snapshot support indefinitely unless external usage is fully
   retired.
