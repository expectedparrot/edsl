"""
Storage implementations for object versioning.

Provides BaseObjectStore base class and in-memory implementations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Set, Literal
import json
import uuid

from .utils import _stable_dumps, _sha256
from .models import Commit, Ref


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

    def put_commit(self, commit: Commit, state_id: str) -> None:
        self._commits[commit.commit_id] = commit
        self._commit_to_state[commit.commit_id] = state_id

    def get_commit_state_id(self, commit_id: str) -> str:
        return self._commit_to_state[commit_id]

    def has_ref(self, name: str) -> bool:
        return name in self._refs

    def get_ref(self, name: str) -> Ref:
        return self._refs[name]

    def upsert_ref(self, name: str, commit_id: str, kind: Literal["branch", "tag"] = "branch") -> None:
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

    def list_commits_first_parent(self, start_commit: str, limit: int = 50) -> List[Commit]:
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


# ----------------------------
# In-memory remote implementation
# ----------------------------

@dataclass
class InMemoryRemote(BaseObjectStore):
    """In-memory implementation of a Remote."""
    name: str = "origin"
