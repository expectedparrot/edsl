"""
Data models for object versioning.

Contains Event protocol and core data classes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional, Protocol, Tuple, Literal

from .utils import _utcnow


# ----------------------------
# Events
# ----------------------------

class Event(Protocol):
    """
    An Event describes a change to state.

    Requirements:
    - name: str - event type identifier
    - payload: dict - event data (can be attribute or @property)
    - execute(store) -> new_store - apply event to store
    """
    name: str

    @property
    def payload(self) -> Dict[str, Any]:
        ...

    def execute(self, state: Any) -> Any:
        ...


# ----------------------------
# Commit / Refs
# ----------------------------

@dataclass(frozen=True)
class Commit:
    """Immutable commit record."""
    commit_id: str
    parents: Tuple[str, ...]
    timestamp: datetime
    message: str
    event_name: str
    event_payload: Dict[str, Any]
    author: str = "unknown"


@dataclass(frozen=True)
class Ref:
    """Reference (branch or tag) pointing to a commit."""
    name: str
    commit_id: str
    kind: Literal["branch", "tag"] = "branch"
    updated_at: datetime = field(default_factory=_utcnow)


# ----------------------------
# Result dataclasses
# ----------------------------

@dataclass(frozen=True)
class PushResult:
    """Result of a push operation."""
    remote_name: str
    ref_name: str
    old_commit: Optional[str]
    new_commit: str
    commits_pushed: int
    states_pushed: int


@dataclass(frozen=True)
class PullResult:
    """Result of a pull operation."""
    remote_name: str
    ref_name: str
    old_commit: Optional[str]
    new_commit: str
    commits_fetched: int
    states_fetched: int
    fast_forward: bool


@dataclass(frozen=True)
class Status:
    """Status of a repository."""
    repo_id: str
    head_commit: str
    head_ref: Optional[str]
    is_detached: bool
    has_staged: bool
    staged_events: Tuple[str, ...]
    is_behind: bool
