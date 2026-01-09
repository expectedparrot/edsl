"""
Object versioning module for git-like version control of Python objects.

Provides event-sourced versioning with branch, commit, push/pull operations.

Quick Start:
    from edsl.object_versions import VersionedList, InMemoryRemote

    # Create a versioned list
    vl = VersionedList([{'x': 1}, {'x': 2}])

    # Mutate (returns new instance, original unchanged)
    vl2 = vl.append({'x': 3})
    vl2 = vl2.git_commit("added row")

    # Branch
    vl2 = vl2.git_branch("feature")
    vl2 = vl2.append({'x': 100})
    vl2 = vl2.git_commit("feature work")

    # Checkout
    vl2 = vl2.git_checkout("main")

    # Remote operations
    origin = InMemoryRemote()
    vl2 = vl2.git_add_remote("origin", origin)
    vl2.git_push()

    # Clone
    vl3 = VersionedList.git_clone(origin)

Core Components:
- GitMixin: Mixin to add versioning to any class
- event: Decorator for methods that return Events
- ListStore: Immutable store for list-of-dicts
- VersionedList: Ready-to-use versioned list

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

from .list_store import (
    # Store
    ListStore,

    # Versioned list
    VersionedList,
    create_versioned_list_class,

    # Events (for custom use)
    AppendRowEvent,
    ExtendRowsEvent,
    UpdateRowEvent,
    DeleteRowEvent,
    FilterRowsEvent,
    SortRowsEvent,
    SetMetadataEvent,
    UpdateCellEvent,
    AddColumnEvent,
    DeleteColumnEvent,
    RenameColumnEvent,
)

# Lazy imports for http_remote to avoid loading pydantic/requests at import time
def __getattr__(name):
    if name in ('HTTPRemote', 'ObjectVersionsServer', 'run_server', 'create_app'):
        from . import http_remote
        return getattr(http_remote, name)
    # Lazy imports for versioning modules
    if name in ('SnapshotManager', 'SnapshotConfig', 'SnapshotStats', 'get_snapshot_stats', 'gc_snapshots'):
        from . import snapshot_manager
        return getattr(snapshot_manager, name)
    if name in ('DeltaCompressor', 'Delta', 'DeltaOp', 'compute_delta', 'apply_delta', 'estimate_savings'):
        from . import delta_compression
        return getattr(delta_compression, name)
    if name in ('EventCompactor', 'compact_events', 'analyze_events'):
        from . import event_compaction
        return getattr(event_compaction, name)
    if name in ('TimeTraveler', 'get_history', 'find_commit_at_time', 'diff_commits'):
        from . import time_travel
        return getattr(time_travel, name)
    if name in ('EventValidator', 'validate_event', 'dry_run', 'ValidationResult', 'DryRunResult'):
        from . import validation
        return getattr(validation, name)
    if name in ('MetricsCollector', 'StorageAnalyzer', 'get_collector', 'timed', 'get_metrics_summary'):
        from . import metrics
        return getattr(metrics, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    # Core
    'GitMixin',
    'event',
    'Event',

    # Repo/Remote
    'Repo',
    'InMemoryRepo',
    'Remote',
    'InMemoryRemote',
    'HTTPRemote',
    'ObjectVersionsServer',

    # Data classes
    'Commit',
    'Ref',
    'Status',
    'PushResult',
    'PullResult',

    # Advanced
    'ObjectView',
    'ExpectedParrotGit',
    'init_repo',
    'clone_from_remote',

    # List store
    'ListStore',
    'VersionedList',
    'create_versioned_list_class',

    # Events
    'AppendRowEvent',
    'ExtendRowsEvent',
    'UpdateRowEvent',
    'DeleteRowEvent',
    'FilterRowsEvent',
    'SortRowsEvent',
    'SetMetadataEvent',
    'UpdateCellEvent',
    'AddColumnEvent',
    'DeleteColumnEvent',
    'RenameColumnEvent',

    # HTTP Server
    'run_server',
    'create_app',

    # Snapshot Management
    'SnapshotManager',
    'SnapshotConfig',
    'SnapshotStats',
    'get_snapshot_stats',
    'gc_snapshots',

    # Delta Compression
    'DeltaCompressor',
    'Delta',
    'DeltaOp',
    'compute_delta',
    'apply_delta',
    'estimate_savings',

    # Event Compaction
    'EventCompactor',
    'compact_events',
    'analyze_events',

    # Time Travel
    'TimeTraveler',
    'get_history',
    'find_commit_at_time',
    'diff_commits',

    # Validation
    'EventValidator',
    'validate_event',
    'dry_run',
    'ValidationResult',
    'DryRunResult',

    # Metrics
    'MetricsCollector',
    'StorageAnalyzer',
    'get_collector',
    'timed',
    'get_metrics_summary',
]
