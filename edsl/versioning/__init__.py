"""
Object versioning module for git-like version control of Python objects.

Provides event-sourced versioning with branch, commit, push/pull operations.

Core Components:
- GitMixin: Mixin to add versioning to any class
- event: Decorator for methods that return Events

For custom classes, inherit from GitMixin and define:
- _versioned: Name of the store attribute
- _store_class: The store class (with to_dict/from_dict)
- @event decorated methods that return Event objects
"""

from .core import (
    # Git infrastructure
    GitMixin,
    event,
    Event,
    # Repo and Remote
    Repo,
    InMemoryRepo,
    Remote,
    InMemoryRemote,
    # Data classes
    Commit,
    Ref,
    Status,
    PushResult,
    PullResult,
    # View and facade (for advanced use)
    ObjectView,
    ExpectedParrotGit,
    # Bootstrapping
    init_repo,
    clone_from_remote,
)


# Lazy imports for http_remote to avoid loading pydantic/requests at import time
def __getattr__(name):
    if name in ("HTTPRemote", "ObjectVersionsServer", "run_server", "create_app"):
        from . import http_remote

        return getattr(http_remote, name)
    # Lazy imports for versioning modules
    if name in (
        "SnapshotManager",
        "SnapshotConfig",
        "SnapshotStats",
        "get_snapshot_stats",
        "gc_snapshots",
    ):
        from . import snapshot_manager

        return getattr(snapshot_manager, name)
    if name in (
        "DeltaCompressor",
        "Delta",
        "DeltaOp",
        "compute_delta",
        "apply_delta",
        "estimate_savings",
    ):
        from . import delta_compression

        return getattr(delta_compression, name)
    if name in ("EventCompactor", "compact_events", "analyze_events"):
        from . import event_compaction

        return getattr(event_compaction, name)
    if name in ("TimeTraveler", "get_history", "find_commit_at_time", "diff_commits"):
        from . import time_travel

        return getattr(time_travel, name)
    if name in (
        "EventValidator",
        "validate_event",
        "dry_run",
        "ValidationResult",
        "DryRunResult",
    ):
        from . import validation

        return getattr(validation, name)
    if name in (
        "MetricsCollector",
        "StorageAnalyzer",
        "get_collector",
        "timed",
        "get_metrics_summary",
    ):
        from . import metrics

        return getattr(metrics, name)
    # Exceptions
    if name in (
        "VersioningError",
        "NonFastForwardPushError",
        "StagedChangesError",
        "RefNotFoundError",
        "CommitNotFoundError",
        "RemoteNotFoundError",
        "RemoteAlreadyExistsError",
        "DetachedHeadError",
        "NothingToCommitError",
        "BranchDeleteError",
        "AmbiguousRevisionError",
        "UnknownRevisionError",
        "RemoteRefNotFoundError",
        "PullConflictError",
        "StateNotFoundError",
        "CommitBehindError",
        "InvalidHeadStateError",
    ):
        from . import exceptions

        return getattr(exceptions, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Core
    "GitMixin",
    "event",
    "Event",
    # Repo/Remote
    "Repo",
    "InMemoryRepo",
    "Remote",
    "InMemoryRemote",
    "HTTPRemote",
    "ObjectVersionsServer",
    # Data classes
    "Commit",
    "Ref",
    "Status",
    "PushResult",
    "PullResult",
    # Advanced
    "ObjectView",
    "ExpectedParrotGit",
    "init_repo",
    "clone_from_remote",
    # HTTP Server
    "run_server",
    "create_app",
    # Snapshot Management
    "SnapshotManager",
    "SnapshotConfig",
    "SnapshotStats",
    "get_snapshot_stats",
    "gc_snapshots",
    # Delta Compression
    "DeltaCompressor",
    "Delta",
    "DeltaOp",
    "compute_delta",
    "apply_delta",
    "estimate_savings",
    # Event Compaction
    "EventCompactor",
    "compact_events",
    "analyze_events",
    # Time Travel
    "TimeTraveler",
    "get_history",
    "find_commit_at_time",
    "diff_commits",
    # Validation
    "EventValidator",
    "validate_event",
    "dry_run",
    "ValidationResult",
    "DryRunResult",
    # Metrics
    "MetricsCollector",
    "StorageAnalyzer",
    "get_collector",
    "timed",
    "get_metrics_summary",
    # Exceptions
    "VersioningError",
    "NonFastForwardPushError",
    "StagedChangesError",
    "RefNotFoundError",
    "CommitNotFoundError",
    "RemoteNotFoundError",
    "RemoteAlreadyExistsError",
    "DetachedHeadError",
    "NothingToCommitError",
    "BranchDeleteError",
    "AmbiguousRevisionError",
    "UnknownRevisionError",
    "RemoteRefNotFoundError",
    "PullConflictError",
    "StateNotFoundError",
    "CommitBehindError",
    "InvalidHeadStateError",
]
