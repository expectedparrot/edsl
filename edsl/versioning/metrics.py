"""
Metrics collection for event-sourced storage.

Provides:
- Performance metrics (replay times, event throughput)
- Storage metrics (snapshot sizes, event counts)
- Health indicators
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from datetime import datetime, timedelta
from collections import deque
import time
import json
import threading

if TYPE_CHECKING:
    from .storage import BaseObjectStore


@dataclass
class TimingMetric:
    """A single timing measurement."""
    operation: str
    duration_ms: float
    timestamp: datetime
    details: Optional[Dict[str, Any]] = None


@dataclass
class StorageMetrics:
    """Storage-related metrics."""
    total_commits: int
    total_snapshots: int
    total_events: int
    snapshot_coverage: float  # Percentage of commits with snapshots
    avg_snapshot_size_bytes: float
    total_storage_bytes: int
    estimated_event_only_bytes: int  # Without snapshots


@dataclass
class PerformanceMetrics:
    """Performance-related metrics."""
    avg_replay_time_ms: float
    max_replay_time_ms: float
    avg_events_replayed: float
    max_events_replayed: int
    events_per_second: float
    commits_per_second: float


@dataclass
class HealthStatus:
    """Repository health status."""
    healthy: bool
    issues: List[str]
    recommendations: List[str]
    scores: Dict[str, float]  # 0-100 scores for various aspects


class MetricsCollector:
    """
    Collects and reports metrics for event-sourced storage.

    Thread-safe for use in concurrent environments.
    """

    def __init__(self, max_history: int = 1000):
        """
        Args:
            max_history: Maximum timing samples to keep
        """
        self.max_history = max_history
        self._timings: deque = deque(maxlen=max_history)
        self._lock = threading.Lock()
        self._counters: Dict[str, int] = {
            "commits": 0,
            "events": 0,
            "replays": 0,
            "snapshots_created": 0,
        }
        self._start_time = datetime.now()

    def record_timing(
        self,
        operation: str,
        duration_ms: float,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record a timing measurement."""
        with self._lock:
            self._timings.append(TimingMetric(
                operation=operation,
                duration_ms=duration_ms,
                timestamp=datetime.now(),
                details=details
            ))

    def record_replay(
        self,
        events_replayed: int,
        duration_ms: float,
        commit_id: str
    ) -> None:
        """Record an event replay operation."""
        with self._lock:
            self._counters["replays"] += 1
        self.record_timing("replay", duration_ms, {
            "events_replayed": events_replayed,
            "commit_id": commit_id
        })

    def record_commit(self, event_name: str, duration_ms: float) -> None:
        """Record a commit operation."""
        with self._lock:
            self._counters["commits"] += 1
            self._counters["events"] += 1
        self.record_timing("commit", duration_ms, {"event": event_name})

    def record_snapshot(self, size_bytes: int, duration_ms: float) -> None:
        """Record a snapshot creation."""
        with self._lock:
            self._counters["snapshots_created"] += 1
        self.record_timing("snapshot", duration_ms, {"size_bytes": size_bytes})

    def increment(self, counter: str, amount: int = 1) -> None:
        """Increment a counter."""
        with self._lock:
            self._counters[counter] = self._counters.get(counter, 0) + amount

    def get_timings(
        self,
        operation: Optional[str] = None,
        since: Optional[datetime] = None
    ) -> List[TimingMetric]:
        """Get timing measurements, optionally filtered."""
        with self._lock:
            timings = list(self._timings)

        if operation:
            timings = [t for t in timings if t.operation == operation]
        if since:
            timings = [t for t in timings if t.timestamp >= since]

        return timings

    def get_performance_metrics(
        self,
        window_seconds: int = 300
    ) -> PerformanceMetrics:
        """
        Get performance metrics for recent operations.

        Args:
            window_seconds: Time window to consider (default 5 minutes)
        """
        since = datetime.now() - timedelta(seconds=window_seconds)
        replay_timings = self.get_timings("replay", since)
        commit_timings = self.get_timings("commit", since)

        # Replay metrics
        if replay_timings:
            replay_times = [t.duration_ms for t in replay_timings]
            events_replayed = [
                t.details.get("events_replayed", 0)
                for t in replay_timings
                if t.details
            ]
            avg_replay = sum(replay_times) / len(replay_times)
            max_replay = max(replay_times)
            avg_events = sum(events_replayed) / len(events_replayed) if events_replayed else 0
            max_events = max(events_replayed) if events_replayed else 0
        else:
            avg_replay = 0
            max_replay = 0
            avg_events = 0
            max_events = 0

        # Throughput
        elapsed = window_seconds
        with self._lock:
            commits = self._counters.get("commits", 0)
            events = self._counters.get("events", 0)

        uptime = (datetime.now() - self._start_time).total_seconds()
        effective_elapsed = min(elapsed, uptime) or 1

        return PerformanceMetrics(
            avg_replay_time_ms=avg_replay,
            max_replay_time_ms=max_replay,
            avg_events_replayed=avg_events,
            max_events_replayed=max_events,
            events_per_second=events / effective_elapsed,
            commits_per_second=commits / effective_elapsed
        )

    def get_counters(self) -> Dict[str, int]:
        """Get all counters."""
        with self._lock:
            return dict(self._counters)

    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._timings.clear()
            self._counters = {
                "commits": 0,
                "events": 0,
                "replays": 0,
                "snapshots_created": 0,
            }
            self._start_time = datetime.now()


class StorageAnalyzer:
    """
    Analyzes storage for metrics and health.
    """

    def __init__(self, storage: "BaseObjectStore"):
        self.storage = storage

    def get_storage_metrics(self, head_commit_id: str) -> StorageMetrics:
        """
        Calculate storage metrics for a repository.

        Args:
            head_commit_id: HEAD commit to analyze from
        """
        commits = []
        snapshots = []
        events = 0
        total_snapshot_size = 0

        current = head_commit_id
        while current:
            if not self.storage.has_commit(current):
                break

            commits.append(current)
            commit = self.storage.get_commit(current)

            if commit.event_name != "init":
                events += 1

            if self.storage.has_snapshot(current):
                snapshots.append(current)
                state_id = self.storage.get_commit_state_id(current)
                if state_id:
                    try:
                        state_bytes = self.storage.get_state_bytes(state_id)
                        total_snapshot_size += len(state_bytes)
                    except:
                        pass

            current = commit.parents[0] if commit.parents else None

        total_commits = len(commits)
        total_snapshots = len(snapshots)
        avg_snapshot_size = total_snapshot_size / total_snapshots if total_snapshots else 0

        # Estimate event-only storage (very rough)
        avg_event_size = 200  # bytes per event, rough estimate
        estimated_event_only = events * avg_event_size

        return StorageMetrics(
            total_commits=total_commits,
            total_snapshots=total_snapshots,
            total_events=events,
            snapshot_coverage=total_snapshots / total_commits if total_commits else 0,
            avg_snapshot_size_bytes=avg_snapshot_size,
            total_storage_bytes=total_snapshot_size + estimated_event_only,
            estimated_event_only_bytes=estimated_event_only
        )

    def check_health(self, head_commit_id: str) -> HealthStatus:
        """
        Check repository health and provide recommendations.

        Args:
            head_commit_id: HEAD commit to analyze
        """
        issues = []
        recommendations = []
        scores = {}

        # Get storage metrics
        metrics = self.get_storage_metrics(head_commit_id)

        # Check snapshot coverage
        if metrics.snapshot_coverage < 0.01:  # Less than 1%
            issues.append("Very low snapshot coverage")
            recommendations.append("Create snapshots to improve read performance")
            scores["snapshot_coverage"] = 20
        elif metrics.snapshot_coverage < 0.05:
            recommendations.append("Consider creating more snapshots")
            scores["snapshot_coverage"] = 50
        else:
            scores["snapshot_coverage"] = min(100, metrics.snapshot_coverage * 1000)

        # Check events between snapshots
        _, _, events = self.storage.find_nearest_snapshot(head_commit_id)
        events_since_snapshot = len(events) if events else 0

        if events_since_snapshot > 100:
            issues.append(f"Many events since last snapshot ({events_since_snapshot})")
            recommendations.append("Create a snapshot to reduce replay time")
            scores["replay_efficiency"] = max(0, 100 - events_since_snapshot)
        elif events_since_snapshot > 50:
            recommendations.append("Consider creating a snapshot soon")
            scores["replay_efficiency"] = max(0, 100 - events_since_snapshot)
        else:
            scores["replay_efficiency"] = 100

        # Check total events
        if metrics.total_events > 10000:
            recommendations.append("Consider event compaction to reduce log size")
            scores["event_volume"] = 50
        else:
            scores["event_volume"] = 100

        # Overall health
        avg_score = sum(scores.values()) / len(scores) if scores else 100
        healthy = len(issues) == 0 and avg_score >= 70

        return HealthStatus(
            healthy=healthy,
            issues=issues,
            recommendations=recommendations,
            scores=scores
        )


# Context manager for timing
class Timer:
    """Context manager for timing operations."""

    def __init__(
        self,
        collector: MetricsCollector,
        operation: str,
        details: Optional[Dict[str, Any]] = None
    ):
        self.collector = collector
        self.operation = operation
        self.details = details or {}
        self.start_time = None
        self.duration_ms = None

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args):
        end_time = time.perf_counter()
        self.duration_ms = (end_time - self.start_time) * 1000
        self.collector.record_timing(
            self.operation,
            self.duration_ms,
            self.details
        )

    def add_detail(self, key: str, value: Any) -> None:
        """Add a detail after the timer started."""
        self.details[key] = value


# Global collector instance (can be replaced)
_global_collector = MetricsCollector()


def get_collector() -> MetricsCollector:
    """Get the global metrics collector."""
    return _global_collector


def set_collector(collector: MetricsCollector) -> None:
    """Set the global metrics collector."""
    global _global_collector
    _global_collector = collector


# Convenience functions

def record_timing(operation: str, duration_ms: float, details: Optional[Dict] = None):
    """Record a timing to the global collector."""
    _global_collector.record_timing(operation, duration_ms, details)


def timed(operation: str, details: Optional[Dict] = None) -> Timer:
    """Create a timer context manager."""
    return Timer(_global_collector, operation, details)


def get_metrics_summary() -> Dict[str, Any]:
    """Get a summary of all metrics."""
    perf = _global_collector.get_performance_metrics()
    counters = _global_collector.get_counters()

    return {
        "counters": counters,
        "performance": {
            "avg_replay_time_ms": round(perf.avg_replay_time_ms, 2),
            "max_replay_time_ms": round(perf.max_replay_time_ms, 2),
            "avg_events_replayed": round(perf.avg_events_replayed, 1),
            "events_per_second": round(perf.events_per_second, 2),
            "commits_per_second": round(perf.commits_per_second, 2),
        }
    }
