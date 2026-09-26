# AgentList Git Package Accessor Spec

## Purpose

`AgentList.git` provides a Git-backed directory package format for AgentList
objects. The package is a normal Git repository whose working tree contains
human-readable AgentList files.

## Package Path

AgentList Git packages use the `.agent_list.ep` directory suffix.

- `save("customers")` writes `customers.agent_list.ep/`.
- `save("customers.agent_list.ep")` uses the path as-is.
- Paths with other suffixes, such as `customers.json`, are rejected.
- `clone(url, path=...)` requires an explicit local path and applies the same
  suffix rules.

## Layout

```text
customers.agent_list.ep/
  manifest.json
  agents/
    000001.json
    000002.json
  .git/
```

`manifest.json` contains the format name, format version, class name, AgentList
metadata, and `agent_order`. Agent files are JSON dictionaries generated from
`Agent.to_dict(add_edsl_version=False)`.

## Public API

Class-level:

- `AgentList.git.load(path, ref="HEAD")`
- `AgentList.git.open(path)`
- `AgentList.git.clone(url, path, ref="HEAD")`

Instance-level:

- `al.git.save(path=None, message="")`
- `al.git.status()`
- `al.git.validate()`
- `al.git.log()`
- `al.git.diff(*refs)`
- `al.git.branches()`
- `al.git.branch(name)`
- `al.git.checkout(ref)`
- `al.git.remotes()`
- `al.git.remote_add(name, url)`
- `al.git.push(remote=None, branch=None)`
- `al.git.pull(remote=None, branch=None)`

## Git Semantics

All Git operations shell out to the system `git` executable.

- `pull()` uses fast-forward-only pulls.
- `push()` sets upstream when one remote exists and no upstream is configured.
- Git command failures are wrapped in `AgentListGitError`.
- `pull()` and `checkout()` refuse to run on a dirty working tree.
- `save()` refuses to overwrite an existing dirty package.

## Agent File Identity

On save, unchanged agents keep their existing file IDs when possible. Inserting
a new agent should update `agent_order` and add one new file without rewriting
unchanged agent files.

## Validation

`validate()` returns `{"status": "ok", "errors": []}` for a valid package.
Invalid packages return `status="invalid"` with errors for issues such as
missing `manifest.json`, invalid JSON, missing agent files, duplicate IDs,
extra agent JSON files, or manifest count mismatches.
