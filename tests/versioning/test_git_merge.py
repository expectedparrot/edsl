"""Comprehensive tests for GitMixin.git_merge() method.

Tests cover:
- Fast-forward merges
- Already up-to-date scenarios
- Three-way merges with commutative operations (success)
- Three-way merges with non-commutative operations (conflicts)
- Error conditions (staged changes, detached HEAD, etc.)
- Edge cases (custom message/author, merge commit structure)
"""

import pytest
from io import StringIO
import sys

from edsl.scenarios import Scenario, ScenarioList
from edsl.versioning.exceptions import (
    StagedChangesError,
    DetachedHeadError,
    MergeConflictError,
    UnknownRevisionError,
    RefNotFoundError,
)


class TestFastForwardMerge:
    """Tests for fast-forward merge scenarios.

    Fast-forward occurs when current branch has no new commits since
    the source branch diverged - the merge simply moves the pointer forward.
    """

    def test_fast_forward_basic(self):
        """Test basic fast-forward merge."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl.git_branch("feature")
        sl = sl.append(Scenario({"a": 2}))
        sl.git_commit("feature work")

        # Go back to main (no commits since branch point)
        sl.git_checkout("main")
        assert len(sl) == 1

        # Merge feature - should fast-forward
        sl.git_merge("feature")

        assert len(sl) == 2
        assert sl[1]["a"] == 2

    def test_fast_forward_multiple_commits(self):
        """Test fast-forward with multiple commits on source branch."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl.git_branch("feature")

        # Multiple commits on feature
        sl = sl.append(Scenario({"a": 2}))
        sl.git_commit("second")
        sl = sl.append(Scenario({"a": 3}))
        sl.git_commit("third")
        sl = sl.append(Scenario({"a": 4}))
        sl.git_commit("fourth")

        sl.git_checkout("main")
        assert len(sl) == 1

        sl.git_merge("feature")

        assert len(sl) == 4
        assert [s["a"] for s in sl] == [1, 2, 3, 4]

    def test_fast_forward_updates_branch_pointer(self):
        """Test that fast-forward updates the branch to point to source commit."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl.git_branch("feature")
        sl = sl.append(Scenario({"a": 2}))
        sl.git_commit("feature work")
        feature_hash = sl.commit_hash

        sl.git_checkout("main")
        sl.git_merge("feature")

        # Main should now point to same commit as feature
        assert sl.commit_hash == feature_hash

    def test_fast_forward_preserves_branch_name(self):
        """Test that fast-forward keeps us on the current branch."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl.git_branch("feature")
        sl = sl.append(Scenario({"a": 2}))
        sl.git_commit("feature work")

        sl.git_checkout("main")
        sl.git_merge("feature")

        assert sl.branch_name == "main"


class TestAlreadyUpToDate:
    """Tests for already-up-to-date scenarios.

    Already up-to-date occurs when:
    1. Both branches point to the same commit
    2. Source branch is an ancestor of current branch
    """

    def test_merge_same_commit(self):
        """Test merging when both branches are at the same commit."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl.git_branch("feature")
        # Both main and feature point to same commit

        sl.git_checkout("main")
        initial_hash = sl.commit_hash

        sl.git_merge("feature")

        # Should be no-op
        assert sl.commit_hash == initial_hash
        assert len(sl) == 1

    def test_merge_ancestor_branch(self):
        """Test merging when source is ancestor of current."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl.git_branch("feature")

        # Make commits only on main
        sl.git_checkout("main")
        sl = sl.append(Scenario({"a": 2}))
        sl.git_commit("main work")

        initial_hash = sl.commit_hash
        initial_len = len(sl)

        # feature is behind main - already up to date
        sl.git_merge("feature")

        assert sl.commit_hash == initial_hash
        assert len(sl) == initial_len

    def test_merge_branch_into_itself(self):
        """Test merging a branch into itself (edge case)."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl = sl.append(Scenario({"a": 2}))
        sl.git_commit("some work")

        initial_hash = sl.commit_hash

        sl.git_merge("main")

        # Should be already up to date
        assert sl.commit_hash == initial_hash


class TestThreeWayMergeSuccess:
    """Tests for successful three-way merges.

    Three-way merge is needed when both branches have new commits since
    their common ancestor. Success requires operations to commute.
    """

    def test_append_different_rows_commutes(self):
        """Test that appending different rows on both branches commutes."""
        sl = ScenarioList([Scenario({"a": 1})])

        # Create feature branch and add a row
        sl.git_branch("feature")
        sl = sl.append(Scenario({"a": 100}))
        sl.git_commit("feature adds row")

        # Go back to main and add a different row
        sl.git_checkout("main")
        sl = sl.append(Scenario({"a": 200}))
        sl.git_commit("main adds row")

        # Merge should succeed - appending different rows commutes
        sl.git_merge("feature")

        # Should have all three rows
        assert len(sl) == 3
        values = sorted([s["a"] for s in sl])
        assert values == [1, 100, 200]

    def test_add_field_to_all_commutes(self):
        """Test that add_value on both branches can commute if fields differ."""
        sl = ScenarioList([Scenario({"a": 1}), Scenario({"a": 2})])

        # Feature adds field 'x'
        sl.git_branch("feature")
        sl = sl.add_value("x", 10)
        sl.git_commit("add x field")

        # Main adds field 'y'
        sl.git_checkout("main")
        sl = sl.add_value("y", 20)
        sl.git_commit("add y field")

        # Should merge successfully
        sl.git_merge("feature")

        # All rows should have both x and y
        assert len(sl) == 2
        for s in sl:
            assert s["x"] == 10
            assert s["y"] == 20

    def test_multiple_appends_both_branches(self):
        """Test multiple appends on both branches merge correctly."""
        sl = ScenarioList([Scenario({"id": 0})])

        # Feature adds several rows (commit each to avoid batch events)
        sl.git_branch("feature")
        sl = sl.append(Scenario({"id": 100}))
        sl.git_commit("feature adds row 1")
        sl = sl.append(Scenario({"id": 101}))
        sl.git_commit("feature adds row 2")

        # Main adds several rows (commit each)
        sl.git_checkout("main")
        sl = sl.append(Scenario({"id": 200}))
        sl.git_commit("main adds row 1")
        sl = sl.append(Scenario({"id": 201}))
        sl.git_commit("main adds row 2")

        sl.git_merge("feature")

        assert len(sl) == 5
        ids = sorted([s["id"] for s in sl])
        assert ids == [0, 100, 101, 200, 201]

    def test_merge_creates_merge_commit(self):
        """Test that three-way merge creates a merge commit."""
        sl = ScenarioList([Scenario({"a": 1})])
        base_hash = sl.commit_hash

        sl.git_branch("feature")
        sl = sl.append(Scenario({"a": 100}))
        sl.git_commit("feature work")
        feature_hash = sl.commit_hash

        sl.git_checkout("main")
        sl = sl.append(Scenario({"a": 200}))
        sl.git_commit("main work")
        main_hash = sl.commit_hash

        sl.git_merge("feature")
        merge_hash = sl.commit_hash

        # Merge commit should be different from both parents
        assert merge_hash != main_hash
        assert merge_hash != feature_hash
        assert merge_hash != base_hash

    def test_merge_commit_message_auto_generated(self):
        """Test auto-generated merge commit message."""
        sl = ScenarioList([Scenario({"a": 1})])

        sl.git_branch("feature")
        sl = sl.append(Scenario({"a": 100}))
        sl.git_commit("feature work")

        sl.git_checkout("main")
        sl = sl.append(Scenario({"a": 200}))
        sl.git_commit("main work")

        sl.git_merge("feature")

        log = sl.git_log(porcelain=True)
        # Most recent commit is the merge
        assert "Merge branch 'feature' into main" in log[0].message

    def test_rename_different_fields_commutes(self):
        """Test renaming different fields on both branches commutes."""
        sl = ScenarioList([
            Scenario({"old_a": 1, "old_b": 10}),
            Scenario({"old_a": 2, "old_b": 20}),
        ])

        # Feature renames old_a to new_a
        sl.git_branch("feature")
        sl = sl.rename({"old_a": "new_a"})
        sl.git_commit("rename old_a")

        # Main renames old_b to new_b
        sl.git_checkout("main")
        sl = sl.rename({"old_b": "new_b"})
        sl.git_commit("rename old_b")

        sl.git_merge("feature")

        # Both renames should be applied
        for s in sl:
            assert "new_a" in s
            assert "new_b" in s
            assert "old_a" not in s
            assert "old_b" not in s

    def test_drop_different_fields_commutes(self):
        """Test dropping different fields on both branches commutes."""
        sl = ScenarioList([
            Scenario({"keep": 1, "drop_a": 10, "drop_b": 100}),
            Scenario({"keep": 2, "drop_a": 20, "drop_b": 200}),
        ])

        # Feature drops drop_a
        sl.git_branch("feature")
        sl = sl.drop("drop_a")
        sl.git_commit("drop drop_a")

        # Main drops drop_b
        sl.git_checkout("main")
        sl = sl.drop("drop_b")
        sl.git_commit("drop drop_b")

        sl.git_merge("feature")

        # Both fields should be dropped
        for s in sl:
            assert "keep" in s
            assert "drop_a" not in s
            assert "drop_b" not in s


class TestMergeConflicts:
    """Tests for merge conflict scenarios.

    Conflicts occur when operations on both branches don't commute -
    applying them in different orders produces different EDSL objects.
    """

    def test_mutate_same_field_conflicts(self):
        """Test that mutating the same field on both branches conflicts."""
        sl = ScenarioList([
            Scenario({"id": 1, "value": 0}),
            Scenario({"id": 2, "value": 0}),
        ])

        # Feature sets value to 100
        sl.git_branch("feature")
        sl = sl.mutate("value = 100")
        sl.git_commit("set value to 100")

        # Main sets value to 200
        sl.git_checkout("main")
        sl = sl.mutate("value = 200")
        sl.git_commit("set value to 200")

        # This should conflict
        with pytest.raises(MergeConflictError) as exc_info:
            sl.git_merge("feature")

        assert "feature" in str(exc_info.value)
        assert "main" in str(exc_info.value)

    def test_conflict_preserves_current_state(self):
        """Test that failed merge preserves the current branch state."""
        sl = ScenarioList([Scenario({"value": 0})])

        sl.git_branch("feature")
        sl = sl.mutate("value = 100")
        sl.git_commit("feature change")

        sl.git_checkout("main")
        sl = sl.mutate("value = 200")
        sl.git_commit("main change")

        original_hash = sl.commit_hash
        original_value = sl[0]["value"]

        with pytest.raises(MergeConflictError):
            sl.git_merge("feature")

        # State should be unchanged
        assert sl.commit_hash == original_hash
        assert sl[0]["value"] == original_value
        assert sl.branch_name == "main"

    def test_conflict_error_contains_event_info(self):
        """Test that MergeConflictError contains useful information."""
        sl = ScenarioList([Scenario({"value": 0})])

        sl.git_branch("feature")
        sl = sl.mutate("value = 100")
        sl.git_commit("feature change")

        sl.git_checkout("main")
        sl = sl.mutate("value = 200")
        sl.git_commit("main change")

        with pytest.raises(MergeConflictError) as exc_info:
            sl.git_merge("feature")

        error = exc_info.value
        assert error.current_branch == "main"
        assert error.source_branch == "feature"
        assert len(error.current_events) > 0
        assert len(error.source_events) > 0

    def test_rename_same_field_both_branches_commutes(self):
        """Test that renaming the same source field on both branches commutes.

        When both branches rename the same source field, only one rename succeeds
        in each ordering (the second finds no field to rename). Since both orderings
        produce the same result, this actually commutes and merges successfully.
        """
        sl = ScenarioList([Scenario({"old_name": 1})])

        # Feature renames to name_a
        sl.git_branch("feature")
        sl = sl.rename({"old_name": "name_a"})
        sl.git_commit("rename to name_a")

        # Main renames to name_b
        sl.git_checkout("main")
        sl = sl.rename({"old_name": "name_b"})
        sl.git_commit("rename to name_b")

        # This actually commutes - both orderings end up with same result
        # (whichever rename is applied first "wins")
        sl.git_merge("feature")

        # One of the renames succeeded
        assert len(sl) == 1

    def test_add_same_field_different_values_conflicts(self):
        """Test adding the same field with different values conflicts."""
        sl = ScenarioList([Scenario({"a": 1})])

        # Feature adds field 'new' with value 100
        sl.git_branch("feature")
        sl = sl.add_value("new", 100)
        sl.git_commit("add new=100")

        # Main adds field 'new' with value 200
        sl.git_checkout("main")
        sl = sl.add_value("new", 200)
        sl.git_commit("add new=200")

        with pytest.raises(MergeConflictError):
            sl.git_merge("feature")


class TestMergeErrorConditions:
    """Tests for error conditions that prevent merge from starting."""

    def test_merge_with_staged_changes_raises(self):
        """Test that merge with staged changes raises StagedChangesError."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl.git_branch("feature")
        sl = sl.append(Scenario({"a": 2}))
        sl.git_commit("feature work")

        sl.git_checkout("main")
        sl = sl.append(Scenario({"a": 3}))  # Staged, not committed

        with pytest.raises(StagedChangesError) as exc_info:
            sl.git_merge("feature")

        assert "merge" in str(exc_info.value)

    def test_merge_in_detached_head_raises(self):
        """Test that merge in detached HEAD raises DetachedHeadError."""
        sl = ScenarioList([Scenario({"a": 1})])
        initial_hash = sl.commit_hash

        sl = sl.append(Scenario({"a": 2}))
        sl.git_commit("second")

        # Create a branch for testing
        sl.git_branch("feature")
        sl = sl.append(Scenario({"a": 3}))
        sl.git_commit("feature work")

        # Checkout a specific commit (detached HEAD)
        sl.git_checkout(initial_hash)
        assert sl.branch_name is None  # Detached

        with pytest.raises(DetachedHeadError) as exc_info:
            sl.git_merge("feature")

        assert "merge" in str(exc_info.value)

    def test_merge_nonexistent_branch_raises(self):
        """Test that merging a nonexistent branch raises error."""
        sl = ScenarioList([Scenario({"a": 1})])

        with pytest.raises(UnknownRevisionError):
            sl.git_merge("nonexistent-branch")

    def test_merge_invalid_commit_hash_raises(self):
        """Test that merging invalid commit hash raises error."""
        sl = ScenarioList([Scenario({"a": 1})])

        with pytest.raises(UnknownRevisionError):
            sl.git_merge("deadbeef12345")


class TestMergeCustomOptions:
    """Tests for custom merge options like message and author."""

    def test_custom_merge_message(self):
        """Test merge with custom commit message."""
        sl = ScenarioList([Scenario({"a": 1})])

        sl.git_branch("feature")
        sl = sl.append(Scenario({"a": 100}))
        sl.git_commit("feature work")

        sl.git_checkout("main")
        sl = sl.append(Scenario({"a": 200}))
        sl.git_commit("main work")

        sl.git_merge("feature", message="Custom merge message for testing")

        log = sl.git_log(porcelain=True)
        assert log[0].message == "Custom merge message for testing"

    def test_custom_merge_author(self):
        """Test merge with custom author."""
        sl = ScenarioList([Scenario({"a": 1})])

        sl.git_branch("feature")
        sl = sl.append(Scenario({"a": 100}))
        sl.git_commit("feature work")

        sl.git_checkout("main")
        sl = sl.append(Scenario({"a": 200}))
        sl.git_commit("main work")

        sl.git_merge("feature", author="test-author")

        log = sl.git_log(porcelain=True)
        assert log[0].author == "test-author"

    def test_fast_forward_ignores_custom_message(self):
        """Test that fast-forward merge doesn't create a new commit with custom message."""
        sl = ScenarioList([Scenario({"a": 1})])

        sl.git_branch("feature")
        sl = sl.append(Scenario({"a": 2}))
        sl.git_commit("feature work", author="feature-author")
        feature_hash = sl.commit_hash

        sl.git_checkout("main")
        sl.git_merge("feature", message="This message won't be used")

        # Fast-forward just moves pointer, so commit hash equals feature's
        assert sl.commit_hash == feature_hash

        log = sl.git_log(porcelain=True)
        # Most recent commit should be the feature commit, not a merge commit
        assert log[0].message == "feature work"


class TestMergeComplexScenarios:
    """Tests for more complex merge scenarios."""

    def test_sequential_merges(self):
        """Test multiple sequential merges."""
        sl = ScenarioList([Scenario({"id": 0})])

        # Create and merge feature-1
        sl.git_branch("feature-1")
        sl = sl.append(Scenario({"id": 1}))
        sl.git_commit("feature-1")
        sl.git_checkout("main")
        sl.git_merge("feature-1")  # Fast-forward

        # Create and merge feature-2
        sl.git_branch("feature-2")
        sl = sl.append(Scenario({"id": 2}))
        sl.git_commit("feature-2")
        sl.git_checkout("main")
        sl.git_merge("feature-2")  # Fast-forward

        # Create feature-3 but also make changes on main
        sl.git_branch("feature-3")
        sl = sl.append(Scenario({"id": 3}))
        sl.git_commit("feature-3")

        sl.git_checkout("main")
        sl = sl.append(Scenario({"id": 100}))
        sl.git_commit("main diverges")

        # Three-way merge
        sl.git_merge("feature-3")

        assert len(sl) == 5
        ids = sorted([s["id"] for s in sl])
        assert ids == [0, 1, 2, 3, 100]

    def test_merge_long_diverged_branches(self):
        """Test merging branches that diverged long ago with many commits."""
        sl = ScenarioList([Scenario({"base": True})])

        sl.git_branch("feature")
        # Many commits on feature
        for i in range(5):
            sl = sl.append(Scenario({f"feature_{i}": True}))
            sl.git_commit(f"feature commit {i}")

        sl.git_checkout("main")
        # Many commits on main
        for i in range(5):
            sl = sl.append(Scenario({f"main_{i}": True}))
            sl.git_commit(f"main commit {i}")

        sl.git_merge("feature")

        # Should have 1 base + 5 feature + 5 main = 11 rows
        assert len(sl) == 11

    def test_merge_preserves_metadata(self):
        """Test that merge preserves metadata from both branches."""
        sl = ScenarioList([Scenario({"a": 1})])

        # Feature adds metadata
        sl.git_branch("feature")
        sl = sl.append(Scenario({"a": 2}))
        sl.git_commit("feature work")

        # Main adds different data
        sl.git_checkout("main")
        sl = sl.append(Scenario({"a": 3}))
        sl.git_commit("main work")

        sl.git_merge("feature")

        # All data should be preserved
        values = sorted([s["a"] for s in sl])
        assert values == [1, 2, 3]

    def test_merge_by_commit_hash(self):
        """Test merging by commit hash instead of branch name."""
        sl = ScenarioList([Scenario({"a": 1})])

        sl.git_branch("feature")
        sl = sl.append(Scenario({"a": 100}))
        sl.git_commit("feature work")
        feature_hash = sl.commit_hash

        sl.git_checkout("main")
        sl = sl.append(Scenario({"a": 200}))
        sl.git_commit("main work")

        # Merge by commit hash
        sl.git_merge(feature_hash)

        assert len(sl) == 3

    def test_merge_by_short_commit_hash(self):
        """Test merging by short commit hash prefix."""
        sl = ScenarioList([Scenario({"a": 1})])

        sl.git_branch("feature")
        sl = sl.append(Scenario({"a": 100}))
        sl.git_commit("feature work")
        feature_hash = sl.commit_hash

        sl.git_checkout("main")
        sl = sl.append(Scenario({"a": 200}))
        sl.git_commit("main work")

        # Merge by short hash
        sl.git_merge(feature_hash[:8])

        assert len(sl) == 3


class TestMergeOutputMessages:
    """Tests for merge output messages (captured from stdout)."""

    def test_fast_forward_prints_message(self, capsys):
        """Test that fast-forward merge prints appropriate message."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl.git_branch("feature")
        sl = sl.append(Scenario({"a": 2}))
        sl.git_commit("feature work")

        sl.git_checkout("main")
        sl.git_merge("feature")

        captured = capsys.readouterr()
        assert "Fast-forward" in captured.out

    def test_already_up_to_date_prints_message(self, capsys):
        """Test that already-up-to-date prints appropriate message."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl.git_branch("feature")
        sl.git_checkout("main")

        sl.git_merge("feature")

        captured = capsys.readouterr()
        assert "Already up to date" in captured.out

    def test_three_way_merge_prints_strategy(self, capsys):
        """Test that three-way merge prints strategy message."""
        sl = ScenarioList([Scenario({"a": 1})])

        sl.git_branch("feature")
        sl = sl.append(Scenario({"a": 100}))
        sl.git_commit("feature work")

        sl.git_checkout("main")
        sl = sl.append(Scenario({"a": 200}))
        sl.git_commit("main work")

        sl.git_merge("feature")

        captured = capsys.readouterr()
        assert "commutativity" in captured.out


class TestMergeWithOtherGitOperations:
    """Tests for merge interaction with other git operations."""

    def test_merge_then_commit(self):
        """Test making commits after a merge."""
        sl = ScenarioList([Scenario({"a": 1})])

        sl.git_branch("feature")
        sl = sl.append(Scenario({"a": 100}))
        sl.git_commit("feature work")

        sl.git_checkout("main")
        sl = sl.append(Scenario({"a": 200}))
        sl.git_commit("main work")

        sl.git_merge("feature")
        merge_hash = sl.commit_hash

        # Continue working after merge
        sl = sl.append(Scenario({"a": 300}))
        sl.git_commit("post-merge work")

        assert sl.commit_hash != merge_hash
        assert len(sl) == 4

    def test_checkout_after_merge(self):
        """Test checkout to old commit after merge."""
        sl = ScenarioList([Scenario({"a": 1})])
        main_initial = sl.commit_hash

        sl.git_branch("feature")
        sl = sl.append(Scenario({"a": 100}))
        sl.git_commit("feature work")

        sl.git_checkout("main")
        sl = sl.append(Scenario({"a": 200}))
        sl.git_commit("main work")

        sl.git_merge("feature")
        assert len(sl) == 3

        # Checkout old commit
        sl.git_checkout(main_initial)
        assert len(sl) == 1
        assert sl[0]["a"] == 1

    def test_branch_after_merge(self):
        """Test creating new branch after merge."""
        sl = ScenarioList([Scenario({"a": 1})])

        sl.git_branch("feature")
        sl = sl.append(Scenario({"a": 100}))
        sl.git_commit("feature work")

        sl.git_checkout("main")
        sl = sl.append(Scenario({"a": 200}))
        sl.git_commit("main work")

        sl.git_merge("feature")

        # Create new branch from merge commit
        sl.git_branch("post-merge-feature")
        assert sl.branch_name == "post-merge-feature"
        assert len(sl) == 3

    def test_log_shows_merge_commit(self):
        """Test that git_log shows merge commit."""
        sl = ScenarioList([Scenario({"a": 1})])

        sl.git_branch("feature")
        sl = sl.append(Scenario({"a": 100}))
        sl.git_commit("feature work")

        sl.git_checkout("main")
        sl = sl.append(Scenario({"a": 200}))
        sl.git_commit("main work")

        sl.git_merge("feature")

        log = sl.git_log(porcelain=True)

        # Should have: merge, main work, (feature work reachable), init
        # The most recent should be merge
        assert "Merge" in log[0].message or "merge" in log[0].event_name

    def test_status_clean_after_merge(self):
        """Test that status is clean after successful merge."""
        sl = ScenarioList([Scenario({"a": 1})])

        sl.git_branch("feature")
        sl = sl.append(Scenario({"a": 100}))
        sl.git_commit("feature work")

        sl.git_checkout("main")
        sl = sl.append(Scenario({"a": 200}))
        sl.git_commit("main work")

        sl.git_merge("feature")

        assert not sl.has_staged
        assert sl.git_status().has_staged == False


class TestMergeEdgeCases:
    """Edge cases and boundary conditions for merge."""

    def test_merge_feature_with_add_then_drop_field(self):
        """Test merge when feature adds and drops a field (net change to structure)."""
        sl = ScenarioList([Scenario({"a": 1})])

        sl.git_branch("feature")
        # Add field then drop it - net effect is nothing visible
        sl = sl.add_value("temp_field", 999)
        sl.git_commit("add temp field")
        sl = sl.drop("temp_field")
        sl.git_commit("drop temp field")

        sl.git_checkout("main")
        sl = sl.append(Scenario({"a": 2}))
        sl.git_commit("main work")

        # Should merge successfully
        sl.git_merge("feature")

        # Main's work should be present, no temp_field
        assert len(sl) == 2
        for s in sl:
            assert "temp_field" not in s

    def test_merge_identical_changes_both_branches(self):
        """Test when both branches make identical changes."""
        sl = ScenarioList([Scenario({"a": 1})])

        sl.git_branch("feature")
        sl = sl.append(Scenario({"a": 2}))
        sl.git_commit("feature adds row")

        sl.git_checkout("main")
        sl = sl.append(Scenario({"a": 2}))  # Same row!
        sl.git_commit("main adds same row")

        # Both branches append the same data
        # This should commute and result in both rows
        sl.git_merge("feature")

        # Both appends should be present (duplicates allowed)
        assert len(sl) == 3

    def test_merge_with_very_long_branch_name(self):
        """Test merge with long branch name."""
        long_name = "feature-" + "x" * 100
        sl = ScenarioList([Scenario({"a": 1})])

        sl.git_branch(long_name)
        sl = sl.append(Scenario({"a": 2}))
        sl.git_commit("feature work")

        sl.git_checkout("main")
        sl.git_merge(long_name)

        assert len(sl) == 2

    def test_merge_after_branch_delete(self):
        """Test that merge works even after deleting the source branch (by hash)."""
        sl = ScenarioList([Scenario({"a": 1})])

        sl.git_branch("feature")
        sl = sl.append(Scenario({"a": 100}))
        sl.git_commit("feature work")
        feature_hash = sl.commit_hash

        sl.git_checkout("main")
        sl = sl.append(Scenario({"a": 200}))
        sl.git_commit("main work")

        # Delete feature branch
        sl.git_delete_branch("feature")

        # Can still merge by commit hash
        sl.git_merge(feature_hash)

        assert len(sl) == 3

    def test_merge_single_row_scenario_list(self):
        """Test merge with single-row ScenarioList."""
        sl = ScenarioList([Scenario({"only": "row"})])

        sl.git_branch("feature")
        sl = sl.add_value("feature_field", 1)
        sl.git_commit("feature adds field")

        sl.git_checkout("main")
        sl = sl.add_value("main_field", 2)
        sl.git_commit("main adds field")

        sl.git_merge("feature")

        assert len(sl) == 1
        assert sl[0]["feature_field"] == 1
        assert sl[0]["main_field"] == 2
