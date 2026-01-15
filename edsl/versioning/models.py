"""
Data models for object versioning.

Contains Event protocol and core data classes.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol, Tuple, Literal

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
    def payload(self) -> Dict[str, Any]: ...

    def execute(self, state: Any) -> Any: ...


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

    def __str__(self) -> str:
        """Format commit similar to git log output."""
        lines = []
        lines.append(f"commit {self.commit_id}")
        lines.append(f"Author: {self.author}")
        # Format timestamp like git: "Wed Jan 15 01:25:35 2026 +0000"
        ts_str = self.timestamp.strftime("%a %b %d %H:%M:%S %Y %z")
        if not ts_str.endswith("+0000") and self.timestamp.tzinfo is not None:
            # Ensure timezone is shown
            ts_str = self.timestamp.strftime("%a %b %d %H:%M:%S %Y %z")
        lines.append(f"Date:   {ts_str}")
        lines.append("")
        # Indent message like git does
        for msg_line in self.message.split("\n"):
            lines.append(f"    {msg_line}")
        return "\n".join(lines)


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
    is_stale: bool = False  # True when object's data diverged from git state

    def __repr__(self) -> str:
        """Format status similar to git status output."""
        # ANSI color codes (only if TTY)
        use_color = sys.stdout.isatty()
        RED = "\033[31m" if use_color else ""
        YELLOW = "\033[33m" if use_color else ""
        RESET = "\033[0m" if use_color else ""

        lines = []

        # HEAD info
        if self.is_detached:
            lines.append(f"HEAD detached at {self.head_commit[:8]}")
            lines.append('  (use "git_checkout()" to see available branches)')
            lines.append('  (use "git_branch(\'name\')" to create a new branch here)')
        else:
            lines.append(f"On branch {self.head_ref}")

        # Behind status (local branch has advanced since this object was created)
        if self.is_behind:
            lines.append(
                f"Your view is behind '{self.head_ref}' (branch has new commits)."
            )
            lines.append(f'  (use "git_checkout(\'{self.head_ref}\')" to update)')
            lines.append(f'  (use "git_branch(\'name\')" to branch from here)')

        # Stale status (data diverged from git state due to shared mutation)
        if self.is_stale:
            lines.append("")
            lines.append(f"{YELLOW}warning:{RESET} object data has diverged from git state")
            lines.append("  (another reference modified the shared data)")
            lines.append(f'  (use "git_checkout(\'{self.head_ref or "HEAD"}\')" to refresh)')

        # Staged changes
        if self.has_staged:
            lines.append("")
            lines.append("Changes to be committed:")
            lines.append('  (use "git_discard()" to unstage)')
            for event_name in self.staged_events:
                lines.append(f"        {RED}{event_name}{RESET}")
        else:
            lines.append("")
            lines.append("nothing to commit, working tree clean")

        return "\n".join(lines)


@dataclass(frozen=True)
class MergePrepareResult:
    """Result of prepare_merge() - data needed for commutativity test.

    Contains all information needed by GitMixin.git_merge() to:
    1. Materialize EDSL objects in both event orders
    2. Compare hashes for commutativity test
    3. Finalize the merge commit if successful
    """

    source_branch: str
    current_branch: str
    merge_base_id: str
    base_state: Tuple[Dict[str, Any], ...]
    current_events: Tuple[Tuple[str, Dict[str, Any]], ...]
    source_events: Tuple[Tuple[str, Dict[str, Any]], ...]
    current_commit_id: str
    source_commit_id: str
    is_fast_forward: bool
    already_up_to_date: bool
