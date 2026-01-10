"""
Snapshot management for event-sourced storage.

Provides:
- Auto-snapshotting after N events
- Snapshot garbage collection
- Snapshot statistics and coverage analysis
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from .storage import BaseObjectStore


@dataclass
class SnapshotStats:
    """Statistics about snapshots in a repository."""

    total_commits: int
    total_snapshots: int
    snapshot_coverage: float  # Percentage of commits with snapshots
    max_events_to_replay: int  # Worst case replay count
    avg_events_to_replay: float  # Average replay count
    snapshot_commits: List[str]  # Commit IDs with snapshots
    events_since_last_snapshot: int


@dataclass
class SnapshotConfig:
    """Configuration for auto-snapshotting."""

    auto_snapshot_threshold: int = 50  # Create snapshot after N events
    min_snapshot_interval: int = 10  # Minimum commits between snapshots
    keep_snapshots: int = 10  # Number of snapshots to keep during GC


class SnapshotManager:
    """
    Manages snapshots for event-sourced storage.

    Features:
    - Auto-snapshot after N events
    - Garbage collection of old snapshots
    - Statistics and coverage analysis
    """

    def __init__(self, config: Optional[SnapshotConfig] = None):
        self.config = config or SnapshotConfig()

    def should_auto_snapshot(self, storage: "BaseObjectStore", commit_id: str) -> bool:
        """
        Determine if an auto-snapshot should be created.

        Returns True if:
        - Events since last snapshot >= threshold
        - Minimum interval since last snapshot is met
        """
        snapshot_commit, state_id, events = storage.find_nearest_snapshot(commit_id)

        if state_id is None:
            # No snapshot exists - definitely need one
            return True

        events_since = len(events)
        return events_since >= self.config.auto_snapshot_threshold

    def get_stats(
        self, storage: "BaseObjectStore", head_commit_id: str
    ) -> SnapshotStats:
        """
        Calculate snapshot statistics for a repository.

        Walks the commit history to gather statistics about snapshot coverage.
        """
        commits = []
        snapshots = []
        events_to_replay = []

        # Walk commit history
        current = head_commit_id
        while current:
            if not storage.has_commit(current):
                break

            commits.append(current)

            # Check if this commit has a snapshot
            if storage.has_snapshot(current):
                snapshots.append(current)

            # Calculate events to replay for this commit
            _, state_id, events = storage.find_nearest_snapshot(current)
            if state_id is not None:
                events_to_replay.append(len(events))

            # Move to parent
            commit = storage.get_commit(current)
            if commit.parents:
                current = commit.parents[0]
            else:
                current = None

        total_commits = len(commits)
        total_snapshots = len(snapshots)

        # Events since last snapshot (from HEAD)
        _, _, head_events = storage.find_nearest_snapshot(head_commit_id)
        events_since_last = len(head_events) if head_events else 0

        return SnapshotStats(
            total_commits=total_commits,
            total_snapshots=total_snapshots,
            snapshot_coverage=(
                total_snapshots / total_commits if total_commits > 0 else 0
            ),
            max_events_to_replay=max(events_to_replay) if events_to_replay else 0,
            avg_events_to_replay=(
                sum(events_to_replay) / len(events_to_replay) if events_to_replay else 0
            ),
            snapshot_commits=snapshots,
            events_since_last_snapshot=events_since_last,
        )

    def gc_snapshots(
        self,
        storage: "BaseObjectStore",
        head_commit_id: str,
        keep_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Garbage collect old snapshots, keeping only the most recent N.

        Always keeps:
        - The initial commit snapshot (required for replay)
        - The HEAD snapshot (if exists)
        - The most recent N snapshots

        Returns:
            Dict with gc statistics
        """
        keep = keep_count or self.config.keep_snapshots

        # Find all snapshots in order (newest first)
        snapshots_in_order = []
        current = head_commit_id
        initial_commit = None

        while current:
            if not storage.has_commit(current):
                break

            if storage.has_snapshot(current):
                snapshots_in_order.append(current)

            commit = storage.get_commit(current)
            if not commit.parents:
                initial_commit = current
                break
            current = commit.parents[0]

        # Determine which snapshots to keep
        to_keep = set()

        # Always keep initial snapshot
        if initial_commit and storage.has_snapshot(initial_commit):
            to_keep.add(initial_commit)

        # Keep the N most recent
        for commit_id in snapshots_in_order[:keep]:
            to_keep.add(commit_id)

        # Remove snapshots not in keep set
        removed = []
        for commit_id in snapshots_in_order:
            if commit_id not in to_keep:
                state_id = storage.get_commit_state_id(commit_id)
                if state_id:
                    # Remove the state and the mapping
                    if state_id in storage._states:
                        del storage._states[state_id]
                    if commit_id in storage._commit_to_state:
                        del storage._commit_to_state[commit_id]
                    removed.append(commit_id)

        return {
            "snapshots_before": len(snapshots_in_order),
            "snapshots_after": len(snapshots_in_order) - len(removed),
            "snapshots_removed": len(removed),
            "removed_commits": removed,
            "kept_commits": list(to_keep),
        }

    def find_optimal_snapshot_points(
        self, storage: "BaseObjectStore", head_commit_id: str, target_interval: int = 50
    ) -> List[str]:
        """
        Find optimal commits for creating new snapshots.

        Returns commit IDs where snapshots would be beneficial,
        spaced approximately target_interval commits apart.
        """
        # Walk history and find commits at regular intervals
        optimal_points = []
        commits_since_last = 0

        current = head_commit_id
        while current:
            if not storage.has_commit(current):
                break

            commits_since_last += 1

            # Check if this is a good snapshot point
            if commits_since_last >= target_interval:
                if not storage.has_snapshot(current):
                    optimal_points.append(current)
                commits_since_last = 0

            commit = storage.get_commit(current)
            if not commit.parents:
                break
            current = commit.parents[0]

        return optimal_points


# Convenience functions for use without instantiating manager


def should_auto_snapshot(
    storage: "BaseObjectStore", commit_id: str, threshold: int = 50
) -> bool:
    """Check if auto-snapshot should be created."""
    manager = SnapshotManager(SnapshotConfig(auto_snapshot_threshold=threshold))
    return manager.should_auto_snapshot(storage, commit_id)


def get_snapshot_stats(
    storage: "BaseObjectStore", head_commit_id: str
) -> SnapshotStats:
    """Get snapshot statistics."""
    manager = SnapshotManager()
    return manager.get_stats(storage, head_commit_id)


def gc_snapshots(
    storage: "BaseObjectStore", head_commit_id: str, keep_count: int = 10
) -> Dict[str, Any]:
    """Garbage collect old snapshots."""
    manager = SnapshotManager()
    return manager.gc_snapshots(storage, head_commit_id, keep_count)
