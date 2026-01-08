"""
Git-like facade for object versioning.

Provides ObjectView, ExpectedParrotGit, and bootstrapping functions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Set

from .utils import _utcnow, _sha256, _stable_dumps
from .models import Commit, PushResult, Status
from .protocols import Repo, Remote
from .storage import InMemoryRepo


# ----------------------------
# ObjectView
# ----------------------------

@dataclass(frozen=True)
class ObjectView:
    """Immutable view of an object in a repo."""
    repo: Repo
    head_ref: Optional[str] = "main"
    base_commit: Optional[str] = None
    pending_events: Tuple[Tuple[str, Dict[str, Any]], ...] = ()

    def _resolve_base_commit(self) -> str:
        if self.base_commit is not None:
            return self.base_commit
        if self.head_ref is not None:
            return self.repo.get_ref(self.head_ref).commit_id
        raise ValueError("Invalid HEAD state: no base_commit or head_ref")

    def get_base_state(self) -> List[Dict[str, Any]]:
        cid = self._resolve_base_commit()
        sid = self.repo.get_commit_state_id(cid)
        return self.repo.get_state(sid)

    def is_behind(self) -> bool:
        if self.head_ref is None:
            return False
        current_ref_commit = self.repo.get_ref(self.head_ref).commit_id
        return current_ref_commit != self._resolve_base_commit()

    @property
    def commit_hash(self) -> str:
        return self._resolve_base_commit()

    @property
    def has_staged(self) -> bool:
        return len(self.pending_events) > 0


# ----------------------------
# Helper functions
# ----------------------------

def _make_commit_id(
    *,
    repo_id: str,
    parents: Tuple[str, ...],
    event_name: str,
    event_payload: Dict[str, Any],
    state_id: str,
    message: str,
    author: str,
) -> str:
    payload = {
        "repo_id": repo_id,
        "parents": list(parents),
        "event_name": event_name,
        "event_payload": event_payload,
        "state_id": state_id,
        "message": message,
        "author": author,
    }
    return _sha256(_stable_dumps(payload))


def _resolve_commit_prefix(repo: Repo, prefix: str) -> str:
    if repo.has_commit(prefix):
        return prefix
    all_commit_ids = repo.list_all_commit_ids()
    matches = [cid for cid in all_commit_ids if cid.startswith(prefix)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(f"Ambiguous commit prefix: {prefix}")
    raise ValueError(f"Unknown rev: {prefix}")


# ----------------------------
# ExpectedParrotGit facade
# ----------------------------

class ExpectedParrotGit:
    """Git-like operations over an ObjectView."""

    def __init__(self, view: ObjectView, remotes: Optional[Dict[str, Remote]] = None):
        self._view = view
        self._remotes: Dict[str, Remote] = remotes if remotes is not None else {}

    def _with_view(self, new_view: ObjectView) -> "ExpectedParrotGit":
        return ExpectedParrotGit(new_view, remotes=self._remotes)

    @property
    def view(self) -> ObjectView:
        return self._view

    def status(self) -> Status:
        staged_names = tuple(name for name, _ in self._view.pending_events)
        return Status(
            repo_id=self._view.repo.repo_id,
            head_commit=self._view.commit_hash,
            head_ref=self._view.head_ref,
            is_detached=self._view.head_ref is None,
            has_staged=self._view.has_staged,
            staged_events=staged_names,
            is_behind=self._view.is_behind(),
        )

    def log(self, limit: int = 20) -> List[Commit]:
        return self._view.repo.list_commits_first_parent(self._view.commit_hash, limit=limit)

    def checkout(self, rev: str, *, force: bool = False) -> "ExpectedParrotGit":
        if self._view.has_staged and not force:
            raise ValueError("You have staged changes; commit/discard or use force=True")
        repo = self._view.repo
        if repo.has_ref(rev):
            cid = repo.get_ref(rev).commit_id
            new_view = ObjectView(repo=repo, head_ref=rev, base_commit=cid)
            return self._with_view(new_view)
        cid = _resolve_commit_prefix(repo, rev)
        new_view = ObjectView(repo=repo, head_ref=None, base_commit=cid)
        return self._with_view(new_view)

    def branch(self, name: str) -> "ExpectedParrotGit":
        if self._view.has_staged:
            raise ValueError("You have staged changes; commit/discard before branching")
        repo = self._view.repo
        current_commit = self._view.commit_hash
        repo.upsert_ref(name, current_commit, kind="branch")
        new_view = ObjectView(repo=repo, head_ref=name, base_commit=current_commit)
        return self._with_view(new_view)

    def delete_branch(self, name: str) -> "ExpectedParrotGit":
        if name == self._view.head_ref:
            raise ValueError(f"Cannot delete the current branch '{name}'")
        repo = self._view.repo
        if not repo.has_ref(name):
            raise ValueError(f"Branch '{name}' does not exist")
        ref = repo.get_ref(name)
        if ref.kind != "branch":
            raise ValueError(f"'{name}' is a {ref.kind}, not a branch")
        repo.delete_ref(name)
        return self._with_view(self._view)

    def apply_event(self, event_name: str, payload: Dict[str, Any]) -> "ExpectedParrotGit":
        new_pending = self._view.pending_events + ((event_name, dict(payload)),)
        new_view = ObjectView(
            repo=self._view.repo,
            head_ref=self._view.head_ref,
            base_commit=self._view.base_commit,
            pending_events=new_pending,
        )
        return self._with_view(new_view)

    def discard(self) -> "ExpectedParrotGit":
        new_view = ObjectView(
            repo=self._view.repo,
            head_ref=self._view.head_ref,
            base_commit=self._view.base_commit,
            pending_events=(),
        )
        return self._with_view(new_view)

    def commit(self, message: str, *, author: str = "unknown", force: bool = False,
               state: List[Dict[str, Any]]) -> "ExpectedParrotGit":
        if not self._view.pending_events:
            raise ValueError("Nothing to commit (clean).")
        if self._view.head_ref is not None and self._view.is_behind():
            if not force:
                branch = self._view.head_ref
                our_base = self._view.commit_hash[:10]
                current = self._view.repo.get_ref(branch).commit_id[:10]
                raise ValueError(
                    f"Cannot commit: your base commit ({our_base}) is behind "
                    f"'{branch}' ({current}). Use force=True to overwrite."
                )

        repo = self._view.repo
        parent = self._view.commit_hash
        state_id = repo.put_state(state)

        pending = self._view.pending_events
        if len(pending) == 1:
            ev_name, ev_payload = pending[0]
        else:
            ev_name = "batch"
            ev_payload = {"events": [{"name": n, "payload": p} for n, p in pending]}

        commit_id = _make_commit_id(
            repo_id=repo.repo_id,
            parents=(parent,),
            event_name=ev_name,
            event_payload=ev_payload,
            state_id=state_id,
            message=message,
            author=author,
        )
        commit = Commit(
            commit_id=commit_id,
            parents=(parent,),
            timestamp=_utcnow(),
            message=message,
            event_name=ev_name,
            event_payload=dict(ev_payload),
            author=author,
        )
        repo.put_commit(commit, state_id)

        if self._view.head_ref is not None:
            repo.upsert_ref(self._view.head_ref, commit_id, kind="branch")
            new_view = ObjectView(repo=repo, head_ref=self._view.head_ref, base_commit=commit_id)
        else:
            new_view = ObjectView(repo=repo, head_ref=None, base_commit=commit_id)

        return self._with_view(new_view)

    # --- Remote management ---

    def add_remote(self, name: str, remote: Remote) -> "ExpectedParrotGit":
        if name in self._remotes:
            raise ValueError(f"Remote '{name}' already exists")
        new_remotes = dict(self._remotes)
        new_remotes[name] = remote
        return ExpectedParrotGit(self._view, remotes=new_remotes)

    def remove_remote(self, name: str) -> "ExpectedParrotGit":
        if name not in self._remotes:
            raise ValueError(f"Remote '{name}' does not exist")
        new_remotes = dict(self._remotes)
        del new_remotes[name]
        return ExpectedParrotGit(self._view, remotes=new_remotes)

    def list_remotes(self) -> List[str]:
        return sorted(self._remotes.keys())

    # --- Push / Pull ---

    def push(self, remote_name: str = "origin", ref_name: Optional[str] = None,
             *, force: bool = False) -> PushResult:
        if self._view.has_staged:
            raise ValueError("Cannot push with staged changes; commit first")
        if remote_name not in self._remotes:
            raise ValueError(f"Remote '{remote_name}' not found")

        remote = self._remotes[remote_name]
        repo = self._view.repo

        if ref_name is None:
            if self._view.head_ref is None:
                raise ValueError("Cannot push detached HEAD without specifying ref_name")
            ref_name = self._view.head_ref

        if not repo.has_ref(ref_name):
            raise ValueError(f"Local ref '{ref_name}' does not exist")

        local_ref = repo.get_ref(ref_name)
        local_commit_id = local_ref.commit_id

        old_commit: Optional[str] = None
        if remote.has_ref(ref_name):
            old_commit = remote.get_ref(ref_name).commit_id
            if old_commit == local_commit_id:
                return PushResult(remote_name, ref_name, old_commit, local_commit_id, 0, 0)
            if not force and not self._is_ancestor(old_commit, local_commit_id):
                raise ValueError(
                    f"Non-fast-forward push rejected. Remote '{ref_name}' is at "
                    f"{old_commit[:10]}, local is at {local_commit_id[:10]}. Use force=True."
                )

        commits_to_push = self._collect_missing_commits(local_commit_id, remote)
        states_pushed = 0
        for commit in reversed(commits_to_push):
            state_id = repo.get_commit_state_id(commit.commit_id)
            if not remote.has_state(state_id):
                state_bytes = repo.get_state_bytes(state_id)
                remote.put_state_bytes(state_id, state_bytes)
                states_pushed += 1
            remote.put_commit(commit, state_id)

        remote.upsert_ref(ref_name, local_commit_id, kind=local_ref.kind)
        return PushResult(remote_name, ref_name, old_commit, local_commit_id,
                          len(commits_to_push), states_pushed)

    def pull(self, remote_name: str = "origin",
             ref_name: Optional[str] = None) -> "ExpectedParrotGit":
        if self._view.has_staged:
            raise ValueError("Cannot pull with staged changes; commit first")
        if remote_name not in self._remotes:
            raise ValueError(f"Remote '{remote_name}' not found")

        remote = self._remotes[remote_name]
        repo = self._view.repo

        if ref_name is None:
            if self._view.head_ref is None:
                raise ValueError("Cannot pull to detached HEAD without specifying ref_name")
            ref_name = self._view.head_ref

        if not remote.has_ref(ref_name):
            raise ValueError(f"Remote ref '{ref_name}' does not exist")

        remote_ref = remote.get_ref(ref_name)
        remote_commit_id = remote_ref.commit_id

        old_commit: Optional[str] = None
        if repo.has_ref(ref_name):
            old_commit = repo.get_ref(ref_name).commit_id
            if old_commit == remote_commit_id:
                return self

        commits_to_fetch = self._collect_missing_commits_from_remote(remote_commit_id, remote, repo)
        for commit in reversed(commits_to_fetch):
            state_id = remote.get_commit_state_id(commit.commit_id)
            if not repo.has_state(state_id):
                state_bytes = remote.get_state_bytes(state_id)
                repo.put_state_bytes(state_id, state_bytes)
            repo.put_commit(commit, state_id)

        fast_forward = old_commit is None or self._is_ancestor(old_commit, remote_commit_id)
        if not fast_forward:
            raise ValueError(
                f"Pull would result in non-fast-forward. Merge not yet implemented."
            )

        repo.upsert_ref(ref_name, remote_commit_id, kind=remote_ref.kind)
        new_view = ObjectView(repo=repo, head_ref=ref_name, base_commit=remote_commit_id)
        return self._with_view(new_view)

    def fetch(self, remote_name: str = "origin") -> Dict[str, int]:
        if remote_name not in self._remotes:
            raise ValueError(f"Remote '{remote_name}' not found")

        remote = self._remotes[remote_name]
        repo = self._view.repo
        result: Dict[str, int] = {}

        for remote_ref in remote.list_refs():
            commits_to_fetch = self._collect_missing_commits_from_remote(
                remote_ref.commit_id, remote, repo
            )
            for commit in reversed(commits_to_fetch):
                state_id = remote.get_commit_state_id(commit.commit_id)
                if not repo.has_state(state_id):
                    state_bytes = remote.get_state_bytes(state_id)
                    repo.put_state_bytes(state_id, state_bytes)
                repo.put_commit(commit, state_id)

            tracking_ref = f"{remote_name}/{remote_ref.name}"
            repo.upsert_ref(tracking_ref, remote_ref.commit_id, kind=remote_ref.kind)
            result[remote_ref.name] = len(commits_to_fetch)

        return result

    def _is_ancestor(self, ancestor_id: str, descendant_id: str) -> bool:
        repo = self._view.repo
        visited: Set[str] = set()
        to_visit = [descendant_id]
        while to_visit:
            current = to_visit.pop()
            if current == ancestor_id:
                return True
            if current in visited:
                continue
            visited.add(current)
            if repo.has_commit(current):
                commit = repo.get_commit(current)
                to_visit.extend(commit.parents)
        return False

    def _collect_missing_commits(self, start_id: str, remote: Remote) -> List[Commit]:
        repo = self._view.repo
        missing: List[Commit] = []
        visited: Set[str] = set()
        to_visit = [start_id]
        while to_visit:
            current = to_visit.pop()
            if current in visited or remote.has_commit(current):
                continue
            visited.add(current)
            commit = repo.get_commit(current)
            missing.append(commit)
            to_visit.extend(commit.parents)
        return missing

    def _collect_missing_commits_from_remote(
        self, start_id: str, remote: Remote, local_repo: Repo
    ) -> List[Commit]:
        missing: List[Commit] = []
        visited: Set[str] = set()
        to_visit = [start_id]
        while to_visit:
            current = to_visit.pop()
            if current in visited or local_repo.has_commit(current):
                continue
            visited.add(current)
            commit = remote.get_commit(current)
            missing.append(commit)
            to_visit.extend(commit.parents)
        return missing


# ----------------------------
# Bootstrapping
# ----------------------------

def clone_from_remote(remote: Remote, ref_name: str = "main") -> ObjectView:
    """Clone a repository from a remote."""
    if not remote.has_ref(ref_name):
        raise ValueError(f"Remote does not have ref '{ref_name}'")

    local_repo = InMemoryRepo()
    remote_ref = remote.get_ref(ref_name)
    target_commit_id = remote_ref.commit_id

    commits_to_copy: List[Commit] = []
    visited: Set[str] = set()
    to_visit = [target_commit_id]

    while to_visit:
        current = to_visit.pop()
        if current in visited:
            continue
        visited.add(current)
        commit = remote.get_commit(current)
        commits_to_copy.append(commit)
        to_visit.extend(commit.parents)

    for commit in reversed(commits_to_copy):
        state_id = remote.get_commit_state_id(commit.commit_id)
        if not local_repo.has_state(state_id):
            state_bytes = remote.get_state_bytes(state_id)
            local_repo.put_state_bytes(state_id, state_bytes)
        local_repo.put_commit(commit, state_id)

    local_repo.upsert_ref(ref_name, target_commit_id, kind=remote_ref.kind)
    return ObjectView(repo=local_repo, head_ref=ref_name, base_commit=target_commit_id)


def init_repo(rows: List[Dict[str, Any]], *, author: str = "unknown") -> ObjectView:
    """Initialize a new repo with initial state."""
    repo = InMemoryRepo()
    state_id = repo.put_state([dict(r) for r in rows])

    root_commit_id = _make_commit_id(
        repo_id=repo.repo_id,
        parents=(),
        event_name="init",
        event_payload={"rows": "omitted"},
        state_id=state_id,
        message="init",
        author=author,
    )
    root_commit = Commit(
        commit_id=root_commit_id,
        parents=(),
        timestamp=_utcnow(),
        message="init",
        event_name="init",
        event_payload={"note": "initial import"},
        author=author,
    )
    repo.put_commit(root_commit, state_id)
    repo.upsert_ref("main", root_commit_id, kind="branch")

    return ObjectView(repo=repo, head_ref="main", base_commit=root_commit_id)
