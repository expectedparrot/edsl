"""
Storage implementations for object versioning.

Provides BaseObjectStore base class and in-memory implementations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Literal
import json
import uuid

from .utils import _stable_dumps, _sha256
from .models import Commit, Ref


# ----------------------------
# Serialization helpers
# ----------------------------


def _commit_to_dict(c: Commit) -> Dict[str, Any]:
    """Serialize a Commit to a dict."""
    return {
        "commit_id": c.commit_id,
        "parents": list(c.parents),
        "timestamp": c.timestamp.isoformat(),
        "message": c.message,
        "event_name": c.event_name,
        "event_payload": c.event_payload,
        "author": c.author,
    }


def _commit_from_dict(d: Dict[str, Any]) -> Commit:
    """Deserialize a Commit from a dict."""
    return Commit(
        commit_id=d["commit_id"],
        parents=tuple(d["parents"]),
        timestamp=datetime.fromisoformat(d["timestamp"]),
        message=d["message"],
        event_name=d["event_name"],
        event_payload=d["event_payload"],
        author=d.get("author", "unknown"),
    )


def _ref_to_dict(r: Ref) -> Dict[str, Any]:
    """Serialize a Ref to a dict."""
    return {
        "name": r.name,
        "commit_id": r.commit_id,
        "kind": r.kind,
        "updated_at": r.updated_at.isoformat(),
    }


def _ref_from_dict(d: Dict[str, Any]) -> Ref:
    """Deserialize a Ref from a dict."""
    return Ref(
        name=d["name"],
        commit_id=d["commit_id"],
        kind=d.get("kind", "branch"),
        updated_at=(
            datetime.fromisoformat(d["updated_at"])
            if "updated_at" in d
            else datetime.now()
        ),
    )


# ----------------------------
# Shared storage base class
# ----------------------------


@dataclass
class BaseObjectStore:
    """Base class with shared storage logic for repos and remotes."""

    _states: Dict[str, bytes] = field(default_factory=dict)
    _commits: Dict[str, Commit] = field(default_factory=dict)
    _commit_to_state: Dict[str, str] = field(default_factory=dict)
    _refs: Dict[str, Ref] = field(default_factory=dict)

    def has_state(self, state_id: str) -> bool:
        return state_id in self._states

    def get_state_bytes(self, state_id: str) -> bytes:
        return self._states[state_id]

    def put_state_bytes(self, state_id: str, data: bytes) -> None:
        self._states.setdefault(state_id, data)

    def has_commit(self, commit_id: str) -> bool:
        return commit_id in self._commits

    def get_commit(self, commit_id: str) -> Commit:
        return self._commits[commit_id]

    def put_commit(self, commit: Commit, state_id: str = None) -> None:
        """Store a commit, optionally with a state snapshot."""
        self._commits[commit.commit_id] = commit
        if state_id is not None:
            self._commit_to_state[commit.commit_id] = state_id

    def get_commit_state_id(self, commit_id: str) -> Optional[str]:
        """Get state_id for a commit. Returns None if no snapshot exists."""
        return self._commit_to_state.get(commit_id)

    def has_snapshot(self, commit_id: str) -> bool:
        """Check if a commit has a state snapshot."""
        return commit_id in self._commit_to_state

    def find_nearest_snapshot(self, commit_id: str) -> tuple:
        """
        Find the nearest ancestor commit with a snapshot.

        Returns:
            (snapshot_commit_id, state_id, events_to_replay)
            where events_to_replay is a list of (event_name, event_payload)
            from snapshot to target commit (in order).
        """
        events_to_replay = []
        current_id = commit_id

        while current_id:
            # Check if this commit has a snapshot
            state_id = self._commit_to_state.get(current_id)
            if state_id is not None:
                # Found a snapshot - reverse events to get correct order
                events_to_replay.reverse()
                return (current_id, state_id, events_to_replay)

            # No snapshot - record the event and move to parent
            commit = self._commits.get(current_id)
            if commit is None:
                break

            # Don't replay 'init' events (they create empty state)
            if commit.event_name != "init":
                events_to_replay.append((commit.event_name, commit.event_payload))

            # Move to first parent
            if commit.parents:
                current_id = commit.parents[0]
            else:
                current_id = None

        # No snapshot found - return None
        return (None, None, [])

    def has_ref(self, name: str) -> bool:
        return name in self._refs

    def get_ref(self, name: str) -> Ref:
        return self._refs[name]

    def upsert_ref(
        self, name: str, commit_id: str, kind: Literal["branch", "tag"] = "branch"
    ) -> None:
        self._refs[name] = Ref(name=name, commit_id=commit_id, kind=kind)

    def delete_ref(self, name: str) -> None:
        if name not in self._refs:
            raise ValueError(f"Ref '{name}' does not exist")
        del self._refs[name]

    def list_refs(self) -> List[Ref]:
        return sorted(self._refs.values(), key=lambda r: r.name)

    def gc(self) -> Dict[str, int]:
        """Garbage collect unreachable commits and states."""
        reachable_commits: Set[str] = set()
        to_visit: List[str] = [ref.commit_id for ref in self._refs.values()]

        while to_visit:
            cid = to_visit.pop()
            if cid in reachable_commits:
                continue
            reachable_commits.add(cid)
            commit = self._commits.get(cid)
            if commit:
                for parent in commit.parents:
                    if parent not in reachable_commits:
                        to_visit.append(parent)

        all_commits = set(self._commits.keys())
        unreachable_commits = all_commits - reachable_commits

        reachable_states: Set[str] = set()
        for cid in reachable_commits:
            if cid in self._commit_to_state:
                reachable_states.add(self._commit_to_state[cid])

        all_states = set(self._states.keys())
        unreachable_states = all_states - reachable_states

        for cid in unreachable_commits:
            del self._commits[cid]
            if cid in self._commit_to_state:
                del self._commit_to_state[cid]

        for sid in unreachable_states:
            del self._states[sid]

        return {
            "commits_removed": len(unreachable_commits),
            "states_removed": len(unreachable_states),
        }


# ----------------------------
# In-memory repo implementation
# ----------------------------


@dataclass
class InMemoryRepo(BaseObjectStore):
    """Local repository with full Repo protocol support."""

    repo_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def put_state(self, state: List[Dict[str, Any]]) -> str:
        b = _stable_dumps(state)
        state_id = _sha256(b)
        self._states.setdefault(state_id, b)
        return state_id

    def get_state(self, state_id: str) -> List[Dict[str, Any]]:
        b = self._states[state_id]
        rows = json.loads(b.decode("utf-8"))
        return [dict(r) for r in rows]

    def list_commits_first_parent(
        self, start_commit: str, limit: int = 50
    ) -> List[Commit]:
        out: List[Commit] = []
        cur = start_commit
        for _ in range(limit):
            c = self._commits.get(cur)
            if c is None:
                break
            out.append(c)
            if not c.parents:
                break
            cur = c.parents[0]
        return out

    def list_all_commit_ids(self) -> List[str]:
        return list(self._commits.keys())

    def to_dict(self) -> Dict[str, Any]:
        """Serialize repo to dict for disk persistence.

        Returns:
            Dict containing all repo data needed to reconstruct the repo.
        """
        return {
            "repo_id": self.repo_id,
            "states": {k: v.decode("utf-8") for k, v in self._states.items()},
            "commits": {cid: _commit_to_dict(c) for cid, c in self._commits.items()},
            "commit_to_state": dict(self._commit_to_state),
            "refs": {name: _ref_to_dict(r) for name, r in self._refs.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InMemoryRepo":
        """Deserialize repo from dict.

        Args:
            data: Dict from to_dict()

        Returns:
            InMemoryRepo with all data restored.
        """
        repo = cls.__new__(cls)
        repo.repo_id = data["repo_id"]
        repo._states = {k: v.encode("utf-8") for k, v in data["states"].items()}
        repo._commits = {
            cid: _commit_from_dict(c) for cid, c in data["commits"].items()
        }
        repo._commit_to_state = dict(data["commit_to_state"])
        repo._refs = {name: _ref_from_dict(r) for name, r in data["refs"].items()}
        return repo


# ----------------------------
# In-memory remote implementation
# ----------------------------


@dataclass
class InMemoryRemote(BaseObjectStore):
    """In-memory implementation of a Remote."""

    name: str = "origin"
