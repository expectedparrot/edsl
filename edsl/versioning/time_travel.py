"""
Time travel for querying historical state.

Provides:
- Query state at a specific timestamp
- Query state at a specific commit
- Diff between two points in history
- Find commit by various criteria
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING
from datetime import datetime
import re

if TYPE_CHECKING:
    from .storage import BaseObjectStore


@dataclass
class HistoryPoint:
    """A point in the repository history."""

    commit_id: str
    timestamp: datetime
    message: str
    author: Optional[str]
    event_name: str
    has_snapshot: bool


@dataclass
class StateDiff:
    """Difference between two states."""

    from_commit: str
    to_commit: str
    entries_added: int
    entries_removed: int
    entries_modified: int
    fields_added: List[str]
    fields_removed: List[str]
    meta_changes: Dict[str, Tuple[Any, Any]]  # key -> (old_value, new_value)


class TimeTraveler:
    """
    Enables querying historical state of a repository.

    Provides various ways to navigate history and compare states.
    """

    def __init__(self, storage: "BaseObjectStore"):
        self.storage = storage

    def get_history(
        self,
        head_commit_id: str,
        limit: Optional[int] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        author: Optional[str] = None,
        event_filter: Optional[List[str]] = None,
    ) -> List[HistoryPoint]:
        """
        Get commit history with optional filtering.

        Args:
            head_commit_id: Starting commit
            limit: Maximum number of commits to return
            since: Only commits after this time
            until: Only commits before this time
            author: Filter by author
            event_filter: Only include specific event types

        Returns:
            List of HistoryPoint objects
        """
        history = []
        current = head_commit_id
        count = 0

        while current:
            if limit and count >= limit:
                break

            if not self.storage.has_commit(current):
                break

            commit = self.storage.get_commit(current)

            # Apply filters
            if since and commit.timestamp < since:
                break  # History is ordered, can stop here
            if until and commit.timestamp > until:
                current = commit.parents[0] if commit.parents else None
                continue
            if author and commit.author != author:
                current = commit.parents[0] if commit.parents else None
                continue
            if event_filter and commit.event_name not in event_filter:
                current = commit.parents[0] if commit.parents else None
                continue

            history.append(
                HistoryPoint(
                    commit_id=commit.commit_id,
                    timestamp=commit.timestamp,
                    message=commit.message,
                    author=commit.author,
                    event_name=commit.event_name,
                    has_snapshot=self.storage.has_snapshot(current),
                )
            )

            count += 1
            current = commit.parents[0] if commit.parents else None

        return history

    def find_commit_at_time(
        self, head_commit_id: str, target_time: datetime
    ) -> Optional[str]:
        """
        Find the commit that was HEAD at a specific time.

        Returns the most recent commit before or at target_time.
        """
        current = head_commit_id

        while current:
            if not self.storage.has_commit(current):
                break

            commit = self.storage.get_commit(current)

            if commit.timestamp <= target_time:
                return current

            current = commit.parents[0] if commit.parents else None

        return None

    def find_commit_by_message(
        self, head_commit_id: str, pattern: str, regex: bool = False
    ) -> List[str]:
        """
        Find commits by message pattern.

        Args:
            head_commit_id: Starting commit
            pattern: Search pattern
            regex: If True, treat pattern as regex

        Returns:
            List of matching commit IDs
        """
        matches = []
        current = head_commit_id

        if regex:
            compiled = re.compile(pattern, re.IGNORECASE)
            match_fn = lambda msg: compiled.search(msg) is not None
        else:
            pattern_lower = pattern.lower()
            match_fn = lambda msg: pattern_lower in msg.lower()

        while current:
            if not self.storage.has_commit(current):
                break

            commit = self.storage.get_commit(current)
            if match_fn(commit.message):
                matches.append(current)

            current = commit.parents[0] if commit.parents else None

        return matches

    def find_commit_by_event(
        self, head_commit_id: str, event_name: str, nth: int = 1
    ) -> Optional[str]:
        """
        Find the nth occurrence of a specific event type.

        Args:
            head_commit_id: Starting commit
            event_name: Event type to find
            nth: Which occurrence (1 = most recent)

        Returns:
            Commit ID or None
        """
        current = head_commit_id
        count = 0

        while current:
            if not self.storage.has_commit(current):
                break

            commit = self.storage.get_commit(current)
            if commit.event_name == event_name:
                count += 1
                if count == nth:
                    return current

            current = commit.parents[0] if commit.parents else None

        return None

    def get_ancestor(self, commit_id: str, n: int = 1) -> Optional[str]:
        """
        Get the nth ancestor of a commit.

        Args:
            commit_id: Starting commit
            n: How many generations back (1 = parent)

        Returns:
            Ancestor commit ID or None
        """
        current = commit_id

        for _ in range(n):
            if not self.storage.has_commit(current):
                return None
            commit = self.storage.get_commit(current)
            if not commit.parents:
                return None
            current = commit.parents[0]

        return current

    def diff_states(
        self,
        state1: Dict[str, Any],
        state2: Dict[str, Any],
        commit1_id: str = "state1",
        commit2_id: str = "state2",
    ) -> StateDiff:
        """
        Compute difference between two states.

        Args:
            state1: First state (older)
            state2: Second state (newer)
            commit1_id: ID for first state
            commit2_id: ID for second state

        Returns:
            StateDiff describing the changes
        """
        entries1 = state1.get("entries", [])
        entries2 = state2.get("entries", [])
        meta1 = state1.get("meta", {})
        meta2 = state2.get("meta", {})

        # Count entry changes (simple comparison)
        entries_added = max(0, len(entries2) - len(entries1))
        entries_removed = max(0, len(entries1) - len(entries2))

        # Count modified entries
        min_len = min(len(entries1), len(entries2))
        entries_modified = sum(1 for i in range(min_len) if entries1[i] != entries2[i])

        # Find field changes
        fields1 = set()
        fields2 = set()
        for entry in entries1:
            fields1.update(entry.keys())
        for entry in entries2:
            fields2.update(entry.keys())

        fields_added = list(fields2 - fields1)
        fields_removed = list(fields1 - fields2)

        # Meta changes
        meta_changes = {}
        all_keys = set(meta1.keys()) | set(meta2.keys())
        for key in all_keys:
            old_val = meta1.get(key)
            new_val = meta2.get(key)
            if old_val != new_val:
                meta_changes[key] = (old_val, new_val)

        return StateDiff(
            from_commit=commit1_id,
            to_commit=commit2_id,
            entries_added=entries_added,
            entries_removed=entries_removed,
            entries_modified=entries_modified,
            fields_added=fields_added,
            fields_removed=fields_removed,
            meta_changes=meta_changes,
        )

    def get_commits_between(self, from_commit: str, to_commit: str) -> List[str]:
        """
        Get all commits between two points.

        Returns commits from to_commit back to (but not including) from_commit.
        """
        commits = []
        current = to_commit

        while current and current != from_commit:
            if not self.storage.has_commit(current):
                break
            commits.append(current)
            commit = self.storage.get_commit(current)
            current = commit.parents[0] if commit.parents else None

        return commits

    def get_events_between(
        self, from_commit: str, to_commit: str
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """
        Get all events between two commits.

        Returns events needed to transform from_commit state to to_commit state.
        """
        commits = self.get_commits_between(from_commit, to_commit)
        events = []

        for commit_id in reversed(commits):
            commit = self.storage.get_commit(commit_id)
            if commit.event_name != "init":
                events.append((commit.event_name, commit.event_payload))

        return events


# Convenience functions


def get_history(
    storage: "BaseObjectStore", head_commit_id: str, limit: Optional[int] = None
) -> List[HistoryPoint]:
    """Get commit history."""
    return TimeTraveler(storage).get_history(head_commit_id, limit=limit)


def find_commit_at_time(
    storage: "BaseObjectStore", head_commit_id: str, target_time: datetime
) -> Optional[str]:
    """Find commit at specific time."""
    return TimeTraveler(storage).find_commit_at_time(head_commit_id, target_time)


def get_ancestor(
    storage: "BaseObjectStore", commit_id: str, n: int = 1
) -> Optional[str]:
    """Get nth ancestor of commit."""
    return TimeTraveler(storage).get_ancestor(commit_id, n)


def diff_commits(
    storage: "BaseObjectStore",
    state1: Dict[str, Any],
    state2: Dict[str, Any],
    commit1_id: str = "state1",
    commit2_id: str = "state2",
) -> StateDiff:
    """Diff two states."""
    return TimeTraveler(storage).diff_states(state1, state2, commit1_id, commit2_id)
