"""
Git-like facade for object versioning.

Provides ObjectView, ExpectedParrotGit, and bootstrapping functions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Set, Union

from .utils import _utcnow, _sha256, _stable_dumps
from .models import Commit, MergePrepareResult, PushResult, Status
from .protocols import Repo, Remote
from .storage import InMemoryRepo
from .exceptions import (
    NonFastForwardPushError,
    StagedChangesError,
    RefNotFoundError,
    RemoteNotFoundError,
    RemoteAlreadyExistsError,
    DetachedHeadError,
    NothingToCommitError,
    BranchDeleteError,
    AmbiguousRevisionError,
    UnknownRevisionError,
    RemoteRefNotFoundError,
    PullConflictError,
    CommitBehindError,
    InvalidHeadStateError,
    NoMergeBaseError,
)


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
        raise InvalidHeadStateError()

    def get_base_state(self) -> List[Dict[str, Any]]:
        cid = self._resolve_base_commit()
        sid = self.repo.get_commit_state_id(cid)

        if sid is not None and self.repo.has_state(sid):
            # Direct snapshot exists and is available
            return self.repo.get_state(sid)

        # No direct snapshot - need to materialize via event replay
        snapshot_commit_id, state_id, events_to_replay = (
            self.repo.find_nearest_snapshot(cid)
        )

        if state_id is None:
            raise ValueError(
                f"No snapshot found in ancestry of commit {cid}. "
                "The repository state may be corrupted or incomplete."
            )

        if not self.repo.has_state(state_id):
            raise ValueError(
                f"Snapshot {state_id} for commit {snapshot_commit_id} not found in local repo. "
                "Try fetching the repository state again."
            )

        # Load the base snapshot
        state = self.repo.get_state(state_id)

        if not events_to_replay:
            return state

        # Replay events to reach target commit
        # Import here to avoid circular imports
        from edsl.store import Store, create_event, apply_event

        # Convert state list to Store format
        state_dict = state[0] if isinstance(state, list) else state
        store = Store(
            entries=list(state_dict.get("entries", [])),
            meta=dict(state_dict.get("meta", {})),
        )

        for event_name, event_payload in events_to_replay:
            if event_name == "batch":
                # Unpack batch events and apply each sub-event
                sub_events = event_payload.get("events", [])
                for sub in sub_events:
                    sub_event = create_event(sub["event_name"], sub["event_payload"])
                    apply_event(sub_event, store)
            else:
                event = create_event(event_name, event_payload)
                apply_event(event, store)

        # Convert Store back to state format
        return [{"entries": store.entries, "meta": store.meta}]

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
        raise AmbiguousRevisionError(prefix)
    raise UnknownRevisionError(prefix)


_ANCESTOR_PATTERN = re.compile(r"^(.+)~(\d+)$")


def _resolve_ancestor_ref(
    repo: Repo, rev: str, current_commit: str
) -> Optional[str]:
    """Resolve ancestor references like HEAD~1, HEAD~2, main~3, etc.

    Args:
        repo: The repository to resolve against
        rev: The revision string (e.g., "HEAD~1", "main~2")
        current_commit: The current HEAD commit ID (used when rev starts with HEAD)

    Returns:
        The resolved commit ID, or None if rev is not an ancestor reference
    """
    # Handle plain "HEAD"
    if rev == "HEAD":
        return current_commit

    # Check for ~N suffix pattern
    match = _ANCESTOR_PATTERN.match(rev)
    if not match:
        return None

    base_ref = match.group(1)
    generations = int(match.group(2))

    # Resolve the base reference
    if base_ref == "HEAD":
        commit_id = current_commit
    elif repo.has_ref(base_ref):
        commit_id = repo.get_ref(base_ref).commit_id
    elif repo.has_commit(base_ref):
        commit_id = base_ref
    else:
        # Try prefix matching for base ref
        all_commit_ids = repo.list_all_commit_ids()
        matches = [cid for cid in all_commit_ids if cid.startswith(base_ref)]
        if len(matches) == 1:
            commit_id = matches[0]
        elif len(matches) > 1:
            raise AmbiguousRevisionError(base_ref)
        else:
            raise UnknownRevisionError(base_ref)

    # Walk up the parent chain
    for _ in range(generations):
        if not repo.has_commit(commit_id):
            raise UnknownRevisionError(rev)
        commit = repo.get_commit(commit_id)
        if not commit.parents:
            raise UnknownRevisionError(rev)
        commit_id = commit.parents[0]  # Follow first parent

    return commit_id


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
        return self._view.repo.list_commits_first_parent(
            self._view.commit_hash, limit=limit
        )

    def checkout(self, rev: str, *, force: bool = False) -> "ExpectedParrotGit":
        if self._view.has_staged and not force:
            raise StagedChangesError("checkout")
        repo = self._view.repo
        if repo.has_ref(rev):
            cid = repo.get_ref(rev).commit_id
            new_view = ObjectView(repo=repo, head_ref=rev, base_commit=cid)
            return self._with_view(new_view)
        # Try ancestor reference (HEAD~1, main~2, etc.)
        ancestor_cid = _resolve_ancestor_ref(repo, rev, self._view.commit_hash)
        if ancestor_cid is not None:
            new_view = ObjectView(repo=repo, head_ref=None, base_commit=ancestor_cid)
            return self._with_view(new_view)
        cid = _resolve_commit_prefix(repo, rev)
        new_view = ObjectView(repo=repo, head_ref=None, base_commit=cid)
        return self._with_view(new_view)

    def branch(self, name: str) -> "ExpectedParrotGit":
        repo = self._view.repo
        current_commit = self._view.commit_hash
        repo.upsert_ref(name, current_commit, kind="branch")
        # Preserve pending events when switching to new branch (like real git)
        new_view = ObjectView(
            repo=repo,
            head_ref=name,
            base_commit=current_commit,
            pending_events=self._view.pending_events,
        )
        return self._with_view(new_view)

    def delete_branch(self, name: str) -> "ExpectedParrotGit":
        if name == self._view.head_ref:
            raise BranchDeleteError(name, "it is the current branch")
        repo = self._view.repo
        if not repo.has_ref(name):
            raise RefNotFoundError(name)
        ref = repo.get_ref(name)
        if ref.kind != "branch":
            raise BranchDeleteError(name, f"it is a {ref.kind}, not a branch")
        repo.delete_ref(name)
        return self._with_view(self._view)

    def apply_event(
        self, event_name: str, payload: Dict[str, Any]
    ) -> "ExpectedParrotGit":
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

    def commit(
        self,
        message: str,
        *,
        author: str = "unknown",
        force: bool = False,
        state: List[Dict[str, Any]],
    ) -> "ExpectedParrotGit":
        if not self._view.pending_events:
            raise NothingToCommitError()
        if self._view.head_ref is not None and self._view.is_behind():
            if not force:
                branch = self._view.head_ref
                our_base = self._view.commit_hash
                current = self._view.repo.get_ref(branch).commit_id
                raise CommitBehindError(branch, our_base, current)

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
            new_view = ObjectView(
                repo=repo, head_ref=self._view.head_ref, base_commit=commit_id
            )
        else:
            new_view = ObjectView(repo=repo, head_ref=None, base_commit=commit_id)

        return self._with_view(new_view)

    # --- Remote management ---

    def add_remote(self, name: str, remote: Union[Remote, str]) -> "ExpectedParrotGit":
        """Add a remote. Can be a Remote object or URL string."""
        if name in self._remotes:
            raise RemoteAlreadyExistsError(name)
        new_remotes = dict(self._remotes)
        new_remotes[name] = remote
        return ExpectedParrotGit(self._view, remotes=new_remotes)

    def remove_remote(self, name: str) -> "ExpectedParrotGit":
        if name not in self._remotes:
            raise RemoteNotFoundError(name)
        new_remotes = dict(self._remotes)
        del new_remotes[name]
        return ExpectedParrotGit(self._view, remotes=new_remotes)

    def list_remotes(self) -> List[str]:
        return sorted(self._remotes.keys())

    # --- Push / Pull ---

    def push(
        self,
        remote_name: str = "origin",
        ref_name: Optional[str] = None,
        *,
        force: bool = False,
    ) -> PushResult:
        if self._view.has_staged:
            raise StagedChangesError("push")
        if remote_name not in self._remotes:
            raise RemoteNotFoundError(remote_name)

        remote = self._remotes[remote_name]
        repo = self._view.repo

        if ref_name is None:
            if self._view.head_ref is None:
                raise DetachedHeadError("push")
            ref_name = self._view.head_ref

        if not repo.has_ref(ref_name):
            raise RefNotFoundError(ref_name)

        local_ref = repo.get_ref(ref_name)
        local_commit_id = local_ref.commit_id

        old_commit: Optional[str] = None
        if remote.has_ref(ref_name):
            old_commit = remote.get_ref(ref_name).commit_id
            if old_commit == local_commit_id:
                return PushResult(
                    remote_name, ref_name, old_commit, local_commit_id, 0, 0
                )
            if not force and not self._is_ancestor(old_commit, local_commit_id):
                raise NonFastForwardPushError(ref_name, old_commit, local_commit_id)

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
        return PushResult(
            remote_name,
            ref_name,
            old_commit,
            local_commit_id,
            len(commits_to_push),
            states_pushed,
        )

    def pull(
        self, remote_name: str = "origin", ref_name: Optional[str] = None
    ) -> Tuple["ExpectedParrotGit", "PullResult"]:
        from .models import PullResult

        if self._view.has_staged:
            raise StagedChangesError("pull")
        if remote_name not in self._remotes:
            raise RemoteNotFoundError(remote_name)

        remote = self._remotes[remote_name]
        repo = self._view.repo

        if ref_name is None:
            if self._view.head_ref is None:
                raise DetachedHeadError("pull")
            ref_name = self._view.head_ref

        if not remote.has_ref(ref_name):
            raise RemoteRefNotFoundError(remote_name, ref_name)

        remote_ref = remote.get_ref(ref_name)
        remote_commit_id = remote_ref.commit_id

        old_commit: Optional[str] = None
        if repo.has_ref(ref_name):
            old_commit = repo.get_ref(ref_name).commit_id
            if old_commit == remote_commit_id:
                # Already up to date
                result = PullResult(
                    remote_name=remote_name,
                    ref_name=ref_name,
                    old_commit=old_commit,
                    new_commit=remote_commit_id,
                    commits_fetched=0,
                    states_fetched=0,
                    fast_forward=True,
                )
                return self, result

        commits_to_fetch = self._collect_missing_commits_from_remote(
            remote_commit_id, remote, repo
        )
        states_fetched = 0
        for commit in reversed(commits_to_fetch):
            state_id = remote.get_commit_state_id(commit.commit_id)
            if state_id is not None and not repo.has_state(state_id):
                state_bytes = remote.get_state_bytes(state_id)
                repo.put_state_bytes(state_id, state_bytes)
                states_fetched += 1
            repo.put_commit(commit, state_id)

        # Ensure we can reconstruct state at the new HEAD
        # If no local snapshot exists in the ancestry, fetch materialized state from server
        snapshot_commit_id, snapshot_state_id, _ = repo.find_nearest_snapshot(
            remote_commit_id
        )
        if snapshot_state_id is None or not repo.has_state(snapshot_state_id):
            # No usable local snapshot - get materialized state from server
            data = remote.get_commit_data(remote_commit_id)
            state_list = [{"entries": data["entries"], "meta": data["meta"]}]
            state_bytes = _stable_dumps(state_list)
            state_id = _sha256(state_bytes)
            repo.put_state_bytes(state_id, state_bytes)
            # Update the HEAD commit to have this state_id
            head_commit = repo.get_commit(remote_commit_id)
            repo.put_commit(head_commit, state_id)
            states_fetched += 1

        fast_forward = old_commit is None or self._is_ancestor(
            old_commit, remote_commit_id
        )
        if not fast_forward:
            raise PullConflictError(ref_name, old_commit, remote_commit_id)

        repo.upsert_ref(ref_name, remote_commit_id, kind=remote_ref.kind)
        new_view = ObjectView(
            repo=repo, head_ref=ref_name, base_commit=remote_commit_id
        )

        result = PullResult(
            remote_name=remote_name,
            ref_name=ref_name,
            old_commit=old_commit,
            new_commit=remote_commit_id,
            commits_fetched=len(commits_to_fetch),
            states_fetched=states_fetched,
            fast_forward=fast_forward,
        )
        return self._with_view(new_view), result

    def fetch(self, remote_name: str = "origin") -> Dict[str, int]:
        if remote_name not in self._remotes:
            raise RemoteNotFoundError(remote_name)

        remote = self._remotes[remote_name]
        repo = self._view.repo
        result: Dict[str, int] = {}

        for remote_ref in remote.list_refs():
            commits_to_fetch = self._collect_missing_commits_from_remote(
                remote_ref.commit_id, remote, repo
            )
            for commit in reversed(commits_to_fetch):
                state_id = remote.get_commit_state_id(commit.commit_id)
                if state_id is not None and not repo.has_state(state_id):
                    state_bytes = remote.get_state_bytes(state_id)
                    repo.put_state_bytes(state_id, state_bytes)
                repo.put_commit(commit, state_id)

            # Ensure we can reconstruct state at this ref's HEAD
            snapshot_commit_id, snapshot_state_id, _ = repo.find_nearest_snapshot(
                remote_ref.commit_id
            )
            if snapshot_state_id is None or not repo.has_state(snapshot_state_id):
                # No usable local snapshot - get materialized state from server
                data = remote.get_commit_data(remote_ref.commit_id)
                state_list = [{"entries": data["entries"], "meta": data["meta"]}]
                state_bytes = _stable_dumps(state_list)
                state_id = _sha256(state_bytes)
                repo.put_state_bytes(state_id, state_bytes)
                head_commit = repo.get_commit(remote_ref.commit_id)
                repo.put_commit(head_commit, state_id)

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
    # Merge helpers
    # ----------------------------

    def _find_merge_base(self, commit_a: str, commit_b: str) -> Optional[str]:
        """Find the lowest common ancestor (merge base) of two commits.

        Uses BFS to find ancestors of commit_a, then BFS from commit_b
        to find the first commit that's also an ancestor of commit_a.
        """
        repo = self._view.repo

        # Build set of all ancestors of commit_a (including itself)
        ancestors_a: Set[str] = set()
        to_visit = [commit_a]
        while to_visit:
            current = to_visit.pop()
            if current in ancestors_a:
                continue
            ancestors_a.add(current)
            if repo.has_commit(current):
                commit = repo.get_commit(current)
                to_visit.extend(commit.parents)

        # BFS from commit_b to find first common ancestor
        visited: Set[str] = set()
        to_visit = [commit_b]
        while to_visit:
            current = to_visit.pop(0)  # BFS - use queue (pop from front)
            if current in ancestors_a:
                return current  # Found the merge base
            if current in visited:
                continue
            visited.add(current)
            if repo.has_commit(current):
                commit = repo.get_commit(current)
                to_visit.extend(commit.parents)

        return None  # No common ancestor

    def _collect_events_between(
        self, ancestor_id: str, descendant_id: str
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """Collect events from ancestor to descendant in application order.

        Returns list of (event_name, event_payload) tuples ordered from
        oldest to newest (ancestor side to descendant side).

        Excludes the ancestor's event (we start from its state).
        """
        repo = self._view.repo
        events: List[Tuple[str, Dict[str, Any]]] = []

        # Walk from descendant back to ancestor, collecting events
        current_id = descendant_id
        while current_id and current_id != ancestor_id:
            commit = repo.get_commit(current_id)
            # Skip init events as they represent initial state, not a change
            if commit.event_name != "init":
                events.append((commit.event_name, commit.event_payload))
            # Follow first parent (main line)
            current_id = commit.parents[0] if commit.parents else None

        # Reverse to get chronological order (oldest first)
        events.reverse()
        return events

    def _get_state_at_commit(self, commit_id: str) -> List[Dict[str, Any]]:
        """Get materialized state at a specific commit.

        Uses the same approach as ObjectView.get_base_state() but for
        an arbitrary commit rather than the current HEAD.
        """
        repo = self._view.repo

        # Check for direct snapshot first
        sid = repo.get_commit_state_id(commit_id)
        if sid is not None and repo.has_state(sid):
            return repo.get_state(sid)

        # No direct snapshot - need to materialize via event replay
        snapshot_commit_id, state_id, events_to_replay = repo.find_nearest_snapshot(
            commit_id
        )

        if state_id is None:
            raise ValueError(
                f"No snapshot found in ancestry of commit {commit_id}. "
                "The repository state may be corrupted or incomplete."
            )

        # Load the base snapshot
        state = repo.get_state(state_id)

        if not events_to_replay:
            return state

        # Replay events to reach target commit
        from edsl.store import Store, create_event, apply_event

        state_dict = state[0] if isinstance(state, list) else state
        store = Store(
            entries=list(state_dict.get("entries", [])),
            meta=dict(state_dict.get("meta", {})),
        )

        for event_name, event_payload in events_to_replay:
            if event_name == "batch":
                sub_events = event_payload.get("events", [])
                for sub in sub_events:
                    sub_event = create_event(sub["event_name"], sub["event_payload"])
                    apply_event(sub_event, store)
            else:
                event = create_event(event_name, event_payload)
                apply_event(event, store)

        return [{"entries": store.entries, "meta": store.meta}]

    def prepare_merge(self, source_ref: str) -> MergePrepareResult:
        """Prepare data for merge commutativity test.

        This method gathers all the information needed for GitMixin.git_merge()
        to perform the commutativity test on materialized EDSL objects.

        Args:
            source_ref: Branch name or commit hash to merge from

        Returns:
            MergePrepareResult containing:
            - Base state at merge base
            - Events from both branches
            - Commit IDs
            - Fast-forward / already-up-to-date flags

        Raises:
            StagedChangesError: If there are uncommitted changes
            DetachedHeadError: If in detached HEAD state
            RefNotFoundError: If source_ref doesn't exist
            NoMergeBaseError: If branches have no common ancestor
        """
        # Precondition checks
        if self._view.has_staged:
            raise StagedChangesError("merge")

        if self._view.head_ref is None:
            raise DetachedHeadError("merge")

        repo = self._view.repo
        current_branch = self._view.head_ref

        # Resolve source ref to commit
        if repo.has_ref(source_ref):
            source_commit_id = repo.get_ref(source_ref).commit_id
            source_branch_name = source_ref
        else:
            # Try ancestor reference (HEAD~1, main~2, etc.)
            ancestor_cid = _resolve_ancestor_ref(
                repo, source_ref, self._view.commit_hash
            )
            if ancestor_cid is not None:
                source_commit_id = ancestor_cid
                source_branch_name = source_ref
            else:
                source_commit_id = _resolve_commit_prefix(repo, source_ref)
                source_branch_name = source_ref[:10]

        current_commit_id = self._view.commit_hash

        # Already up to date?
        if current_commit_id == source_commit_id:
            return MergePrepareResult(
                source_branch=source_branch_name,
                current_branch=current_branch,
                merge_base_id=current_commit_id,
                base_state=(),
                current_events=(),
                source_events=(),
                current_commit_id=current_commit_id,
                source_commit_id=source_commit_id,
                is_fast_forward=False,
                already_up_to_date=True,
            )

        # Find merge base
        merge_base_id = self._find_merge_base(current_commit_id, source_commit_id)
        if merge_base_id is None:
            raise NoMergeBaseError(current_branch, source_branch_name)

        # Fast-forward check: if current is ancestor of source
        if merge_base_id == current_commit_id:
            return MergePrepareResult(
                source_branch=source_branch_name,
                current_branch=current_branch,
                merge_base_id=merge_base_id,
                base_state=(),
                current_events=(),
                source_events=(),
                current_commit_id=current_commit_id,
                source_commit_id=source_commit_id,
                is_fast_forward=True,
                already_up_to_date=False,
            )

        # If source is ancestor of current, already up to date
        if merge_base_id == source_commit_id:
            return MergePrepareResult(
                source_branch=source_branch_name,
                current_branch=current_branch,
                merge_base_id=merge_base_id,
                base_state=(),
                current_events=(),
                source_events=(),
                current_commit_id=current_commit_id,
                source_commit_id=source_commit_id,
                is_fast_forward=False,
                already_up_to_date=True,
            )

        # Three-way merge needed - collect data for commutativity test
        current_events = self._collect_events_between(merge_base_id, current_commit_id)
        source_events = self._collect_events_between(merge_base_id, source_commit_id)
        merge_base_state = self._get_state_at_commit(merge_base_id)

        return MergePrepareResult(
            source_branch=source_branch_name,
            current_branch=current_branch,
            merge_base_id=merge_base_id,
            base_state=tuple(merge_base_state),
            current_events=tuple(current_events),
            source_events=tuple(source_events),
            current_commit_id=current_commit_id,
            source_commit_id=source_commit_id,
            is_fast_forward=False,
            already_up_to_date=False,
        )

    def finalize_merge(
        self,
        prep: MergePrepareResult,
        final_state: List[Dict[str, Any]],
        *,
        message: Optional[str] = None,
        author: str = "unknown",
    ) -> "ExpectedParrotGit":
        """Finalize merge after commutativity test passes.

        Creates a merge commit with two parents pointing to the current
        and source branches.

        Args:
            prep: The MergePrepareResult from prepare_merge()
            final_state: The materialized state to commit
            message: Custom merge commit message (auto-generated if None)
            author: Author of the merge commit

        Returns:
            New ExpectedParrotGit with merge commit as HEAD
        """
        repo = self._view.repo
        current_branch = self._view.head_ref

        # Handle fast-forward case
        if prep.is_fast_forward:
            repo.upsert_ref(current_branch, prep.source_commit_id, kind="branch")
            new_view = ObjectView(
                repo=repo, head_ref=current_branch, base_commit=prep.source_commit_id
            )
            return self._with_view(new_view)

        # Auto-generate message if not provided
        if message is None:
            message = f"Merge branch '{prep.source_branch}' into {current_branch}"

        # Store the final state
        state_id = repo.put_state(final_state)

        # Create merge commit with two parents
        merge_commit_id = _make_commit_id(
            repo_id=repo.repo_id,
            parents=(prep.current_commit_id, prep.source_commit_id),
            event_name="merge",
            event_payload={
                "source_branch": prep.source_branch,
                "target_branch": current_branch,
                "merge_base": prep.merge_base_id,
            },
            state_id=state_id,
            message=message,
            author=author,
        )

        merge_commit = Commit(
            commit_id=merge_commit_id,
            parents=(prep.current_commit_id, prep.source_commit_id),
            timestamp=_utcnow(),
            message=message,
            event_name="merge",
            event_payload={
                "source_branch": prep.source_branch,
                "target_branch": current_branch,
                "merge_base": prep.merge_base_id,
            },
            author=author,
        )

        repo.put_commit(merge_commit, state_id)
        repo.upsert_ref(current_branch, merge_commit_id, kind="branch")

        new_view = ObjectView(
            repo=repo, head_ref=current_branch, base_commit=merge_commit_id
        )
        return self._with_view(new_view)


# ----------------------------
# Bootstrapping
# ----------------------------


def clone_from_remote(remote: Remote, ref_name: str = "main") -> ObjectView:
    """Clone a repository from a remote."""
    if not remote.has_ref(ref_name):
        raise RemoteRefNotFoundError("remote", ref_name)

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
        if state_id is not None and not local_repo.has_state(state_id):
            state_bytes = remote.get_state_bytes(state_id)
            local_repo.put_state_bytes(state_id, state_bytes)
        elif state_id is None:
            # No snapshot for this commit - fetch materialized state from server
            commit_data = remote.get_commit_data(commit.commit_id)
            if commit_data:
                # commit_data has {entries, meta, ...} - wrap as single row for Store format
                store_data = {
                    "entries": commit_data.get("entries", []),
                    "meta": commit_data.get("meta", {}),
                }
                state_id = local_repo.put_state([store_data])
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
