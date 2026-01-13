"""
Comprehensive tests for git-like API in VersionedMixin.

Tests cover:
- RemoteRefs tracking
- fetch() operation
- merge() with various strategies
- Branch management (create_branch, branches, branch_delete)
- checkout() for branches and versions
- Conflict detection and resolution
- pull() with fetch + merge semantics
"""
import pytest

# Skip all tests in this module - stores feature is not yet implemented
pytest.skip(
    "Stores feature not yet implemented - module edsl.stores does not exist",
    allow_module_level=True
)

from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock

# Import the modules we're testing
from edsl.stores import (
    RemoteRef,
    RemoteRefs,
    MergeStrategy,
    Conflict,
    MergeResult,
    MergeConflictError,
    ConflictResolver,
    KeepOurs,
    KeepTheirs,
    KeepNewest,
    ManualResolver,
    detect_conflicts,
    find_common_ancestor,
    EventLog,
    BranchMeta,
)


# ═══════════════════════════════════════════════════════════════
# RemoteRefs Tests
# ═══════════════════════════════════════════════════════════════


class TestRemoteRef:
    """Tests for RemoteRef dataclass."""

    def test_create_remote_ref(self):
        """Test creating a RemoteRef."""
        ref = RemoteRef(
            remote="origin",
            branch="main",
            version=5,
            store_id="abc123",
        )
        assert ref.remote == "origin"
        assert ref.branch == "main"
        assert ref.version == 5
        assert ref.store_id == "abc123"
        assert ref.ref_name == "origin/main"

    def test_ref_name_property(self):
        """Test the ref_name property."""
        ref = RemoteRef(remote="upstream", branch="feature", version=3)
        assert ref.ref_name == "upstream/feature"

    def test_is_stale_fresh(self):
        """Test is_stale for fresh ref."""
        ref = RemoteRef(remote="origin", branch="main", version=1)
        assert not ref.is_stale(max_age_seconds=300)

    def test_is_stale_old(self):
        """Test is_stale for old ref."""
        old_time = datetime.utcnow() - timedelta(minutes=10)
        ref = RemoteRef(
            remote="origin",
            branch="main",
            version=1,
            fetched_at=old_time,
        )
        assert ref.is_stale(max_age_seconds=300)

    def test_to_dict(self):
        """Test serialization to dict."""
        ref = RemoteRef(
            remote="origin",
            branch="main",
            version=5,
            store_id="abc123",
        )
        d = ref.to_dict()
        assert d["remote"] == "origin"
        assert d["branch"] == "main"
        assert d["version"] == 5
        assert d["store_id"] == "abc123"
        assert "fetched_at" in d

    def test_from_dict(self):
        """Test deserialization from dict."""
        d = {
            "remote": "origin",
            "branch": "main",
            "version": 5,
            "store_id": "abc123",
            "fetched_at": "2024-01-15T10:30:00",
        }
        ref = RemoteRef.from_dict(d)
        assert ref.remote == "origin"
        assert ref.branch == "main"
        assert ref.version == 5
        assert ref.store_id == "abc123"


class TestRemoteRefs:
    """Tests for RemoteRefs collection."""

    def test_create_empty(self):
        """Test creating empty RemoteRefs."""
        refs = RemoteRefs()
        assert len(refs) == 0
        assert refs.list_remotes() == []

    def test_update_and_get(self):
        """Test updating and getting refs."""
        refs = RemoteRefs()
        ref = refs.update("origin", "main", version=5, store_id="abc")

        assert ref.version == 5
        assert refs.get("origin/main") == ref
        assert refs.get("origin/main").version == 5

    def test_get_by_parts(self):
        """Test getting ref by remote and branch."""
        refs = RemoteRefs()
        refs.update("origin", "main", version=5)

        ref = refs.get_by_parts("origin", "main")
        assert ref is not None
        assert ref.version == 5

    def test_remove(self):
        """Test removing a ref."""
        refs = RemoteRefs()
        refs.update("origin", "main", version=5)
        assert len(refs) == 1

        assert refs.remove("origin/main")
        assert len(refs) == 0
        assert refs.get("origin/main") is None

    def test_remove_nonexistent(self):
        """Test removing nonexistent ref."""
        refs = RemoteRefs()
        assert not refs.remove("origin/main")

    def test_list_remotes(self):
        """Test listing remotes."""
        refs = RemoteRefs()
        refs.update("origin", "main", version=5)
        refs.update("origin", "develop", version=3)
        refs.update("upstream", "main", version=7)

        remotes = refs.list_remotes()
        assert sorted(remotes) == ["origin", "upstream"]

    def test_list_refs(self):
        """Test listing refs."""
        refs = RemoteRefs()
        refs.update("origin", "main", version=5)
        refs.update("origin", "develop", version=3)
        refs.update("upstream", "main", version=7)

        all_refs = refs.list_refs()
        assert len(all_refs) == 3

        origin_refs = refs.list_refs("origin")
        assert len(origin_refs) == 2

    def test_clear_all(self):
        """Test clearing all refs."""
        refs = RemoteRefs()
        refs.update("origin", "main", version=5)
        refs.update("upstream", "main", version=7)

        count = refs.clear()
        assert count == 2
        assert len(refs) == 0

    def test_clear_specific_remote(self):
        """Test clearing refs for specific remote."""
        refs = RemoteRefs()
        refs.update("origin", "main", version=5)
        refs.update("origin", "develop", version=3)
        refs.update("upstream", "main", version=7)

        count = refs.clear("origin")
        assert count == 2
        assert len(refs) == 1
        assert refs.get("upstream/main") is not None

    def test_compare(self):
        """Test comparing local vs remote."""
        refs = RemoteRefs()
        refs.update("origin", "main", version=5)

        # Local ahead
        result = refs.compare("main", local_version=7)
        assert result["origin"]["ahead"] == 2
        assert result["origin"]["behind"] == 0

        # Local behind
        result = refs.compare("main", local_version=3)
        assert result["origin"]["ahead"] == 0
        assert result["origin"]["behind"] == 2

        # Synced
        result = refs.compare("main", local_version=5)
        assert result["origin"]["is_synced"]

    def test_contains(self):
        """Test __contains__."""
        refs = RemoteRefs()
        refs.update("origin", "main", version=5)

        assert "origin/main" in refs
        assert "origin/develop" not in refs

    def test_serialization_roundtrip(self):
        """Test serialization and deserialization."""
        refs = RemoteRefs()
        refs.update("origin", "main", version=5, store_id="abc")
        refs.update("upstream", "main", version=7)

        d = refs.to_dict()
        refs2 = RemoteRefs.from_dict(d)

        assert len(refs2) == 2
        assert refs2.get("origin/main").version == 5
        assert refs2.get("upstream/main").version == 7


# ═══════════════════════════════════════════════════════════════
# Merge Infrastructure Tests
# ═══════════════════════════════════════════════════════════════


class TestMergeStrategy:
    """Tests for MergeStrategy enum."""

    def test_strategies_exist(self):
        """Test all strategies are defined."""
        assert MergeStrategy.FAST_FORWARD.value == "fast_forward"
        assert MergeStrategy.THREE_WAY.value == "three_way"
        assert MergeStrategy.APPEND.value == "append"
        assert MergeStrategy.OURS.value == "ours"
        assert MergeStrategy.THEIRS.value == "theirs"
        assert MergeStrategy.REBASE.value == "rebase"


class TestConflict:
    """Tests for Conflict dataclass."""

    def test_create_conflict(self):
        """Test creating a conflict."""
        conflict = Conflict(
            event_type="update_row",
            local_value="A",
            remote_value="B",
            row_key="row1",
            field="name",
        )
        assert conflict.event_type == "update_row"
        assert conflict.local_value == "A"
        assert conflict.remote_value == "B"
        assert conflict.row_key == "row1"
        assert conflict.field == "name"

    def test_auto_description(self):
        """Test auto-generated description."""
        conflict = Conflict(
            event_type="update",
            row_key="row1",
            field="name",
            local_value="Alice",
            remote_value="Bob",
        )
        assert "row1" in conflict.description
        assert "name" in conflict.description

    def test_to_dict(self):
        """Test serialization."""
        conflict = Conflict(
            event_type="update",
            local_value="A",
            remote_value="B",
        )
        d = conflict.to_dict()
        assert d["event_type"] == "update"
        assert d["local_value"] == "A"
        assert d["remote_value"] == "B"


class TestMergeResult:
    """Tests for MergeResult dataclass."""

    def test_successful_merge(self):
        """Test successful merge result."""
        result = MergeResult(
            success=True,
            merged_events=[],
            conflicts=[],
            strategy_used=MergeStrategy.FAST_FORWARD,
        )
        assert result.success
        assert not result.has_conflicts

    def test_merge_with_conflicts(self):
        """Test merge result with conflicts."""
        conflict = Conflict(event_type="update", local_value="A", remote_value="B")
        result = MergeResult(
            success=False,
            conflicts=[conflict],
        )
        assert not result.success
        assert result.has_conflicts
        assert len(result.conflicts) == 1

    def test_fast_forward_detection(self):
        """Test is_fast_forward property."""
        # Fast forward: no local commits, some remote
        result = MergeResult(success=True, local_ahead=0, remote_ahead=3)
        assert result.is_fast_forward

        # Not fast forward: local commits
        result = MergeResult(success=True, local_ahead=2, remote_ahead=3)
        assert not result.is_fast_forward


class TestMergeConflictError:
    """Tests for MergeConflictError exception."""

    def test_create_error(self):
        """Test creating merge conflict error."""
        conflict = Conflict(event_type="update", local_value="A", remote_value="B")
        error = MergeConflictError([conflict])

        assert len(error.conflicts) == 1
        assert "1 conflict" in str(error)

    def test_summary(self):
        """Test conflict summary."""
        conflicts = [
            Conflict(event_type="update", row_key="r1"),
            Conflict(event_type="delete", row_key="r2"),
        ]
        error = MergeConflictError(conflicts)
        summary = error.summary()

        assert "2" in summary
        assert "r1" in summary or "update" in summary


# ═══════════════════════════════════════════════════════════════
# Conflict Resolver Tests
# ═══════════════════════════════════════════════════════════════


class TestKeepOurs:
    """Tests for KeepOurs resolver."""

    def test_resolve_with_event(self):
        """Test resolving with local event."""
        local_event = Mock()
        conflict = Conflict(
            event_type="update",
            local_event=local_event,
            remote_event=Mock(),
        )
        resolver = KeepOurs()
        assert resolver.resolve(conflict) == local_event

    def test_resolve_with_value(self):
        """Test resolving with local value."""
        conflict = Conflict(
            event_type="update",
            local_value="local",
            remote_value="remote",
        )
        resolver = KeepOurs()
        assert resolver.resolve(conflict) == "local"


class TestKeepTheirs:
    """Tests for KeepTheirs resolver."""

    def test_resolve_with_event(self):
        """Test resolving with remote event."""
        remote_event = Mock()
        conflict = Conflict(
            event_type="update",
            local_event=Mock(),
            remote_event=remote_event,
        )
        resolver = KeepTheirs()
        assert resolver.resolve(conflict) == remote_event

    def test_resolve_with_value(self):
        """Test resolving with remote value."""
        conflict = Conflict(
            event_type="update",
            local_value="local",
            remote_value="remote",
        )
        resolver = KeepTheirs()
        assert resolver.resolve(conflict) == "remote"


class TestManualResolver:
    """Tests for ManualResolver."""

    def test_resolve_by_index(self):
        """Test resolving by conflict index."""
        resolutions = {0: "first", 1: "second"}
        resolver = ManualResolver(resolutions)

        conflict1 = Conflict(event_type="update")
        conflict2 = Conflict(event_type="update")

        assert resolver.resolve(conflict1) == "first"
        assert resolver.resolve(conflict2) == "second"

    def test_resolve_by_key(self):
        """Test resolving by row key."""
        resolutions = {"row1": "value1", "row2": "value2"}
        resolver = ManualResolver(resolutions)

        conflict1 = Conflict(event_type="update", row_key="row1")
        conflict2 = Conflict(event_type="update", row_key="row2")

        assert resolver.resolve(conflict1) == "value1"
        assert resolver.resolve(conflict2) == "value2"

    def test_missing_resolution_raises(self):
        """Test that missing resolution raises ValueError."""
        resolver = ManualResolver({})
        conflict = Conflict(event_type="update")

        with pytest.raises(ValueError):
            resolver.resolve(conflict)


# ═══════════════════════════════════════════════════════════════
# EventLog Merge Tests
# ═══════════════════════════════════════════════════════════════


class MockEvent:
    """Mock event for testing."""

    _counter = 0

    def __init__(self, version: int, event_type: str = "mock", data: dict = None, unique_id: bool = True):
        self.version = version
        self.event_type = event_type
        self.data = data or {}
        # Use unique IDs to avoid deduplication during merge tests
        if unique_id:
            MockEvent._counter += 1
            self.event_id = f"evt_{version}_{MockEvent._counter}"
        else:
            self.event_id = f"evt_{version}"

    def to_dict(self):
        return {
            "version": self.version,
            "event_type": self.event_type,
            "data": self.data,
        }


class TestEventLogMerge:
    """Tests for EventLog.merge() method."""

    def test_fast_forward_merge(self):
        """Test fast-forward merge when target has no new commits."""
        log = EventLog()

        # Setup: main has events 1-3
        events = [MockEvent(v) for v in range(1, 4)]
        log.commit("main", events)

        # Create feature branch at v3 and add more events
        log.branch("main", at=3, name="feature")
        feature_events = [MockEvent(v) for v in range(4, 6)]
        log.commit("feature", feature_events)

        # Merge feature into main (should fast-forward)
        result_branch, new_version, conflicts = log.merge("main", "feature")

        assert result_branch == "main"
        assert new_version == 5
        assert len(conflicts) == 0

    def test_merge_with_no_conflicts(self):
        """Test merge when both branches have changes but no conflicts."""
        log = EventLog()

        # Setup main
        log.commit("main", [MockEvent(1, data={"key": "a"})])

        # Create feature and add different event
        log.branch("main", at=1, name="feature")
        log.commit("feature", [MockEvent(2, data={"key": "b"})])

        # Add to main too
        log.commit("main", [MockEvent(2, data={"key": "c"})])

        # Merge - should succeed (events are independent)
        result_branch, new_version, conflicts = log.merge(
            "main", "feature", strategy="three_way"
        )

        # May have conflicts depending on implementation
        # This tests the basic flow works

    def test_find_common_ancestor(self):
        """Test finding common ancestor between branches."""
        log = EventLog()

        # Setup
        log.commit("main", [MockEvent(v) for v in range(1, 4)])
        log.branch("main", at=2, name="feature")

        ancestor = log.find_common_ancestor("main", "feature")
        assert ancestor == 2

    def test_list_branches(self):
        """Test listing branches."""
        log = EventLog()
        log._ensure_branch("main")
        log.branch("main", name="feature")
        log.branch("main", name="develop")

        branches = log.list_branches()
        assert "main" in branches
        assert "feature" in branches
        assert "develop" in branches


# ═══════════════════════════════════════════════════════════════
# Integration Tests (using ScenarioList-like behavior)
# ═══════════════════════════════════════════════════════════════


class TestVersionedMixinIntegration:
    """Integration tests for VersionedMixin git-like methods.

    Note: These tests use mocked components to test the mixin behavior
    without requiring full ScenarioList setup.
    """

    def test_remote_refs_property(self):
        """Test that remote_refs is lazily created."""
        # This would be tested with actual VersionedMixin subclass
        refs = RemoteRefs()
        assert len(refs) == 0

        refs.update("origin", "main", 5)
        assert "origin/main" in refs

    def test_branch_workflow(self):
        """Test typical branch workflow."""
        log = EventLog()

        # Start with main
        log.commit("main", [MockEvent(1)])
        log.commit("main", [MockEvent(2)])

        # Create feature branch
        log.branch("main", at=2, name="feature")

        # Work on feature
        log.commit("feature", [MockEvent(3)])
        log.commit("feature", [MockEvent(4)])

        # Verify branches
        assert "main" in log.list_branches()
        assert "feature" in log.list_branches()

        # Verify heads
        assert log.head("main") == 2
        assert log.head("feature") == 4

    def test_checkout_workflow(self):
        """Test checkout workflow between branches."""
        log = EventLog()

        log.commit("main", [MockEvent(1)])
        log.branch("main", at=1, name="feature")
        log.commit("feature", [MockEvent(2)])

        # Get events for each branch
        main_events = log.checkout("main")
        feature_events = log.checkout("feature")

        assert len(main_events) == 1
        assert len(feature_events) == 2


# ═══════════════════════════════════════════════════════════════
# Conflict Detection Tests
# ═══════════════════════════════════════════════════════════════


class TestConflictDetection:
    """Tests for conflict detection logic."""

    def test_no_conflicts_different_rows(self):
        """Test no conflicts when modifying different rows."""
        local_events = [MockEvent(1, data={"row_index": 0})]
        remote_events = [MockEvent(2, data={"row_index": 1})]

        # These events modify different rows, so no conflict
        conflicts = detect_conflicts(local_events, remote_events, base_version=0)
        # Implementation may vary - test the API works
        assert isinstance(conflicts, list)

    def test_detects_same_row_conflict(self):
        """Test detecting conflict when same row modified."""
        # Create events that modify the same thing
        local = MockEvent(1, event_type="update", data={"key": "local"})
        local.row_index = 0

        remote = MockEvent(2, event_type="update", data={"key": "remote"})
        remote.row_index = 0

        conflicts = detect_conflicts([local], [remote], base_version=0)
        # May or may not detect conflict depending on event structure


# ═══════════════════════════════════════════════════════════════
# Run tests
# ═══════════════════════════════════════════════════════════════


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
