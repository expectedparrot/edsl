"""Tests for event-sourcing behavior in versioned objects."""

import pytest

from edsl.scenarios import Scenario, ScenarioList


class TestEventDecorator:
    """Tests for the @event decorator behavior."""

    def test_event_returns_new_instance(self):
        """Test that event methods return new instances (immutability)."""
        sl1 = ScenarioList([Scenario({"a": 1})])

        sl2 = sl1.append(Scenario({"a": 2}))

        # Should be different instances
        assert sl1 is not sl2

        # Original unchanged
        assert len(sl1) == 1

        # New has the change
        assert len(sl2) == 2

    def test_event_creates_pending(self):
        """Test that event methods create pending events."""
        sl = ScenarioList([Scenario({"a": 1})])

        assert not sl.has_staged

        sl = sl.append(Scenario({"a": 2}))

        assert sl.has_staged
        pending = sl.git_pending()
        assert len(pending) == 1

    def test_multiple_events_chain(self):
        """Test chaining multiple event methods."""
        sl = ScenarioList([Scenario({"a": 1})])

        sl = sl.append(Scenario({"a": 2}))
        sl = sl.append(Scenario({"a": 3}))
        sl = sl.append(Scenario({"a": 4}))

        assert len(sl) == 4
        pending = sl.git_pending()
        assert len(pending) == 3

    def test_commit_batches_events(self):
        """Test that commit batches multiple pending events."""
        sl = ScenarioList([Scenario({"a": 1})])

        sl = sl.append(Scenario({"a": 2}))
        sl = sl.append(Scenario({"a": 3}))
        sl.git_commit("batch commit")

        # Should be one commit with batched events
        log = sl.git_log(porcelain=True)
        assert log[0].message == "batch commit"


class TestImmutability:
    """Tests for immutable operations."""

    def test_append_immutable(self):
        """Test append doesn't modify original."""
        sl1 = ScenarioList([Scenario({"a": 1})])
        hash1 = sl1.commit_hash

        sl2 = sl1.append(Scenario({"a": 2}))

        # Original unchanged
        assert len(sl1) == 1
        assert sl1.commit_hash == hash1
        assert not sl1.has_staged

    def test_filter_immutable(self):
        """Test filter doesn't modify original."""
        sl1 = ScenarioList([Scenario({"a": 1}), Scenario({"a": 2})])

        sl2 = sl1.filter("a == 2")

        assert len(sl1) == 2
        assert len(sl2) == 1

    def test_select_immutable(self):
        """Test select doesn't modify original."""
        sl1 = ScenarioList([Scenario({"a": 1, "b": 2})])

        sl2 = sl1.select("a")

        assert "b" in sl1[0]
        assert "b" not in sl2[0]


class TestStateReconstruction:
    """Tests for state reconstruction from events."""

    def test_checkout_reconstructs_state(self):
        """Test checkout correctly reconstructs state from history."""
        sl = ScenarioList([Scenario({"step": 0})])
        commit0 = sl.commit_hash

        sl = sl.append(Scenario({"step": 1}))
        sl.git_commit("step 1")
        commit1 = sl.commit_hash

        sl = sl.append(Scenario({"step": 2}))
        sl.git_commit("step 2")
        commit2 = sl.commit_hash

        # Verify current state
        assert len(sl) == 3

        # Go back to step 1
        sl.git_checkout(commit1)
        assert len(sl) == 2
        assert sl[1]["step"] == 1

        # Go back to step 0
        sl.git_checkout(commit0)
        assert len(sl) == 1
        assert sl[0]["step"] == 0

        # Go forward to step 2
        sl.git_checkout(commit2)
        assert len(sl) == 3
        assert sl[2]["step"] == 2

    def test_branch_isolation(self):
        """Test branches maintain isolated states."""
        sl = ScenarioList([Scenario({"base": True})])

        # Create feature branch and make changes
        sl.git_branch("feature")
        sl = sl.append(Scenario({"feature": True}))
        sl.git_commit("feature work")

        # Go back to main and make different changes
        sl.git_checkout("main")
        sl = sl.append(Scenario({"main": True}))
        sl.git_commit("main work")

        # Verify main state
        assert len(sl) == 2
        assert sl[1].get("main") is True
        assert sl[1].get("feature") is None

        # Verify feature state
        sl.git_checkout("feature")
        assert len(sl) == 2
        assert sl[1].get("feature") is True
        assert sl[1].get("main") is None


class TestEventTypes:
    """Tests for different event types."""

    def test_append_event(self):
        """Test append creates correct event."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl = sl.append(Scenario({"a": 2}))

        pending = sl.git_pending()
        assert pending[0][0] == "append_row"

    def test_filter_event(self):
        """Test filter creates correct event."""
        sl = ScenarioList([Scenario({"a": 1}), Scenario({"a": 2})])
        sl = sl.filter("a == 2")

        pending = sl.git_pending()
        assert pending[0][0] == "remove_rows"

    def test_rename_event(self):
        """Test rename creates correct event."""
        sl = ScenarioList([Scenario({"old_name": 1})])
        sl = sl.rename({"old_name": "new_name"})

        pending = sl.git_pending()
        assert pending[0][0] == "rename_fields"

    def test_add_value_event(self):
        """Test add_value creates correct event."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl = sl.add_value("b", 2)

        pending = sl.git_pending()
        assert pending[0][0] == "add_field_to_all_entries"

    def test_transform_event(self):
        """Test transform creates correct event."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl = sl.transform("a", lambda x: x * 2)

        pending = sl.git_pending()
        assert pending[0][0] == "transform_field"


class TestHistoryIntegrity:
    """Tests for history integrity."""

    def test_commit_ids_unique(self):
        """Test all commit IDs are unique."""
        sl = ScenarioList([Scenario({"a": 1})])

        for i in range(5):
            sl = sl.append(Scenario({"a": i + 10}))
            sl.git_commit(f"commit {i}")

        log = sl.git_log(porcelain=True)
        commit_ids = [c.commit_id for c in log]

        assert len(commit_ids) == len(set(commit_ids))

    def test_parent_chain(self):
        """Test commits have correct parent chain."""
        sl = ScenarioList([Scenario({"a": 1})])

        sl = sl.append(Scenario({"a": 2}))
        sl.git_commit("second")

        sl = sl.append(Scenario({"a": 3}))
        sl.git_commit("third")

        log = sl.git_log(porcelain=True)

        # Each commit should have the previous as parent
        assert log[0].parents[0] == log[1].commit_id
        assert log[1].parents[0] == log[2].commit_id

    def test_timestamps_ordered(self):
        """Test commits have ordered timestamps."""
        sl = ScenarioList([Scenario({"a": 1})])

        for i in range(3):
            sl = sl.append(Scenario({"a": i + 10}))
            sl.git_commit(f"commit {i}")

        log = sl.git_log(porcelain=True)

        # Timestamps should be in descending order (most recent first)
        for i in range(len(log) - 1):
            assert log[i].timestamp >= log[i + 1].timestamp
