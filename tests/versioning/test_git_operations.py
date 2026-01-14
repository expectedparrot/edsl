"""Tests for GitMixin git operations (commit, branch, checkout, etc.)."""

import pytest

from edsl.scenarios import Scenario, ScenarioList
from edsl.versioning.exceptions import (
    StagedChangesError,
    NothingToCommitError,
    BranchDeleteError,
    RefNotFoundError,
    UnknownRevisionError,
)


class TestGitCommit:
    """Tests for git_commit method."""

    def test_commit_creates_new_commit(self):
        """Test that committing creates a new commit."""
        sl = ScenarioList([Scenario({"a": 1})])
        initial_hash = sl.commit_hash

        sl = sl.append(Scenario({"a": 2}))
        sl.git_commit("added entry")

        assert sl.commit_hash != initial_hash

    def test_commit_with_message(self):
        """Test commit message is recorded."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl = sl.append(Scenario({"a": 2}))
        sl.git_commit("my custom message")

        log = sl.git_log()
        assert log[0].message == "my custom message"

    def test_commit_with_author(self):
        """Test commit author is recorded."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl = sl.append(Scenario({"a": 2}))
        sl.git_commit("test", author="john")

        log = sl.git_log()
        assert log[0].author == "john"

    def test_commit_nothing_raises_error(self):
        """Test committing with no changes raises error."""
        sl = ScenarioList([Scenario({"a": 1})])
        # No changes made

        with pytest.raises(NothingToCommitError):
            sl.git_commit("empty commit")

    def test_commit_clears_pending(self):
        """Test that commit clears pending events."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl = sl.append(Scenario({"a": 2}))

        assert sl.has_staged
        sl.git_commit("commit")
        assert not sl.has_staged

    def test_multiple_commits(self):
        """Test multiple sequential commits."""
        sl = ScenarioList([Scenario({"a": 1})])

        sl = sl.append(Scenario({"a": 2}))
        sl.git_commit("second")

        sl = sl.append(Scenario({"a": 3}))
        sl.git_commit("third")

        sl = sl.append(Scenario({"a": 4}))
        sl.git_commit("fourth")

        log = sl.git_log()
        # Should have 4 commits: init + 3 we made
        assert len(log) == 4
        assert log[0].message == "fourth"
        assert log[1].message == "third"
        assert log[2].message == "second"


class TestGitDiscard:
    """Tests for git_discard method."""

    def test_discard_removes_pending_changes(self):
        """Test discard removes pending events."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl = sl.append(Scenario({"a": 2}))

        assert sl.has_staged
        assert len(sl) == 2

        sl.git_discard()

        assert not sl.has_staged
        assert len(sl) == 1  # Back to original

    def test_discard_restores_data(self):
        """Test discard restores original data."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl = sl.append(Scenario({"a": 2}))
        sl = sl.append(Scenario({"a": 3}))

        sl.git_discard()

        assert len(sl) == 1
        assert sl[0]["a"] == 1

    def test_discard_on_clean_state(self):
        """Test discard on clean state does nothing harmful."""
        sl = ScenarioList([Scenario({"a": 1})])

        # Should not raise, just print "Nothing to discard"
        sl.git_discard()

        assert len(sl) == 1
        assert not sl.has_staged


class TestGitBranch:
    """Tests for git_branch method."""

    def test_create_branch(self):
        """Test creating a new branch."""
        sl = ScenarioList([Scenario({"a": 1})])

        sl.git_branch("feature")

        assert sl.branch_name == "feature"

    def test_branch_preserves_data(self):
        """Test branching preserves current data."""
        sl = ScenarioList([Scenario({"a": 1}), Scenario({"a": 2})])

        sl.git_branch("feature")

        assert len(sl) == 2
        assert sl[0]["a"] == 1

    def test_branch_from_branch(self):
        """Test creating branch from another branch."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl.git_branch("feature-1")
        sl = sl.append(Scenario({"a": 2}))
        sl.git_commit("feature-1 work")

        sl.git_branch("feature-1-sub")

        assert sl.branch_name == "feature-1-sub"
        assert len(sl) == 2

    def test_branch_with_staged_changes_raises(self):
        """Test branching with staged changes raises error."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl = sl.append(Scenario({"a": 2}))  # Staged change

        with pytest.raises(StagedChangesError):
            sl.git_branch("feature")


class TestGitCheckout:
    """Tests for git_checkout method."""

    def test_checkout_branch(self):
        """Test checking out a branch."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl.git_branch("feature")
        sl = sl.append(Scenario({"a": 2}))
        sl.git_commit("feature work")

        sl.git_checkout("main")

        assert sl.branch_name == "main"
        assert len(sl) == 1

    def test_checkout_updates_data(self):
        """Test checkout updates data to match branch."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl.git_branch("feature")
        sl = sl.append(Scenario({"a": 2}))
        sl.git_commit("feature")

        # Checkout main - should have 1 entry
        sl.git_checkout("main")
        assert len(sl) == 1

        # Checkout feature - should have 2 entries
        sl.git_checkout("feature")
        assert len(sl) == 2

    def test_checkout_commit_hash(self):
        """Test checking out by commit hash."""
        sl = ScenarioList([Scenario({"a": 1})])
        initial_hash = sl.commit_hash

        sl = sl.append(Scenario({"a": 2}))
        sl.git_commit("second")

        sl.git_checkout(initial_hash)

        assert sl.branch_name is None  # Detached HEAD
        assert len(sl) == 1

    def test_checkout_short_hash(self):
        """Test checking out by short commit hash."""
        sl = ScenarioList([Scenario({"a": 1})])
        initial_hash = sl.commit_hash

        sl = sl.append(Scenario({"a": 2}))
        sl.git_commit("second")

        # Use first 8 characters
        sl.git_checkout(initial_hash[:8])

        assert len(sl) == 1

    def test_checkout_nonexistent_raises(self):
        """Test checkout of nonexistent ref raises error."""
        sl = ScenarioList([Scenario({"a": 1})])

        with pytest.raises(UnknownRevisionError):
            sl.git_checkout("nonexistent-branch")

    def test_checkout_with_staged_raises(self):
        """Test checkout with staged changes raises error."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl.git_branch("feature")
        sl.git_checkout("main")

        sl = sl.append(Scenario({"a": 2}))  # Staged change

        with pytest.raises(StagedChangesError):
            sl.git_checkout("feature")

    def test_checkout_force_discards_staged(self):
        """Test checkout with force=True discards staged changes."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl.git_branch("feature")
        sl = sl.append(Scenario({"a": 2}))
        sl.git_commit("feature work")

        sl.git_checkout("main")
        sl = sl.append(Scenario({"a": 999}))  # Staged change

        sl.git_checkout("feature", force=True)

        assert sl.branch_name == "feature"
        assert len(sl) == 2


class TestGitDeleteBranch:
    """Tests for git_delete_branch method."""

    def test_delete_branch(self):
        """Test deleting a branch."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl.git_branch("feature")
        sl.git_checkout("main")

        sl.git_delete_branch("feature")

        branches = sl.git_branches()
        assert "feature" not in " ".join(branches)

    def test_delete_current_branch_raises(self):
        """Test deleting current branch raises error."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl.git_branch("feature")  # Now on feature

        with pytest.raises(BranchDeleteError):
            sl.git_delete_branch("feature")

    def test_delete_nonexistent_raises(self):
        """Test deleting nonexistent branch raises error."""
        sl = ScenarioList([Scenario({"a": 1})])

        with pytest.raises(RefNotFoundError):
            sl.git_delete_branch("nonexistent")


class TestGitStatus:
    """Tests for git_status method."""

    def test_status_returns_status_object(self):
        """Test git_status returns Status object."""
        sl = ScenarioList([Scenario({"a": 1})])

        status = sl.git_status()

        assert hasattr(status, "head_commit")
        assert hasattr(status, "head_ref")
        assert hasattr(status, "has_staged")

    def test_status_shows_staged(self):
        """Test status shows staged changes."""
        sl = ScenarioList([Scenario({"a": 1})])

        assert not sl.git_status().has_staged

        sl = sl.append(Scenario({"a": 2}))

        assert sl.git_status().has_staged

    def test_status_shows_branch(self):
        """Test status shows current branch."""
        sl = ScenarioList([Scenario({"a": 1})])

        assert sl.git_status().head_ref == "main"

        sl.git_branch("feature")

        assert sl.git_status().head_ref == "feature"


class TestGitLog:
    """Tests for git_log method."""

    def test_log_returns_commits(self):
        """Test git_log returns list of commits."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl = sl.append(Scenario({"a": 2}))
        sl.git_commit("second")

        log = sl.git_log()

        assert len(log) >= 2
        assert all(hasattr(c, "commit_id") for c in log)
        assert all(hasattr(c, "message") for c in log)

    def test_log_order(self):
        """Test log is in reverse chronological order."""
        sl = ScenarioList([Scenario({"a": 1})])

        sl = sl.append(Scenario({"a": 2}))
        sl.git_commit("second")

        sl = sl.append(Scenario({"a": 3}))
        sl.git_commit("third")

        log = sl.git_log()

        assert log[0].message == "third"
        assert log[1].message == "second"

    def test_log_limit(self):
        """Test log limit parameter."""
        sl = ScenarioList([Scenario({"a": 1})])

        for i in range(10):
            sl = sl.append(Scenario({"a": i + 10}))
            sl.git_commit(f"commit {i}")

        # Should have 11 commits total (init + 10)
        full_log = sl.git_log(limit=100)
        assert len(full_log) == 11

        limited_log = sl.git_log(limit=3)
        assert len(limited_log) == 3


class TestGitBranches:
    """Tests for git_branches method."""

    def test_branches_returns_list(self):
        """Test git_branches returns list of branch names."""
        sl = ScenarioList([Scenario({"a": 1})])

        branches = sl.git_branches()

        assert isinstance(branches, list)
        assert any("main" in b for b in branches)

    def test_branches_marks_current(self):
        """Test current branch is marked with asterisk."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl.git_branch("feature")

        branches = sl.git_branches()

        # Current branch (feature) should have asterisk
        assert any("* feature" in b for b in branches)
        assert any("main" in b and "*" not in b for b in branches)

    def test_branches_lists_all(self):
        """Test all branches are listed."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl.git_branch("feature-1")
        sl.git_checkout("main")
        sl.git_branch("feature-2")
        sl.git_checkout("main")
        sl.git_branch("feature-3")

        branches = sl.git_branches()

        branch_str = " ".join(branches)
        assert "main" in branch_str
        assert "feature-1" in branch_str
        assert "feature-2" in branch_str
        assert "feature-3" in branch_str


class TestGitPending:
    """Tests for git_pending method."""

    def test_pending_empty_when_clean(self):
        """Test pending is empty when no staged changes."""
        sl = ScenarioList([Scenario({"a": 1})])

        pending = sl.git_pending()

        assert pending == []

    def test_pending_shows_events(self):
        """Test pending shows staged events."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl = sl.append(Scenario({"a": 2}))

        pending = sl.git_pending()

        assert len(pending) == 1
        assert pending[0][0] == "append_row"  # Event name

    def test_pending_multiple_events(self):
        """Test pending with multiple staged events."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl = sl.append(Scenario({"a": 2}))
        sl = sl.append(Scenario({"a": 3}))

        pending = sl.git_pending()

        assert len(pending) == 2


class TestHasStaged:
    """Tests for has_staged property."""

    def test_has_staged_false_initially(self):
        """Test has_staged is False on new object."""
        sl = ScenarioList([Scenario({"a": 1})])

        assert not sl.has_staged

    def test_has_staged_true_after_change(self):
        """Test has_staged is True after making changes."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl = sl.append(Scenario({"a": 2}))

        assert sl.has_staged

    def test_has_staged_false_after_commit(self):
        """Test has_staged is False after commit."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl = sl.append(Scenario({"a": 2}))
        sl.git_commit("commit")

        assert not sl.has_staged


class TestCommitHash:
    """Tests for commit_hash property."""

    def test_commit_hash_is_string(self):
        """Test commit_hash returns a string."""
        sl = ScenarioList([Scenario({"a": 1})])

        assert isinstance(sl.commit_hash, str)
        assert len(sl.commit_hash) > 0

    def test_commit_hash_changes_on_commit(self):
        """Test commit_hash changes after commit."""
        sl = ScenarioList([Scenario({"a": 1})])
        hash1 = sl.commit_hash

        sl = sl.append(Scenario({"a": 2}))
        sl.git_commit("change")
        hash2 = sl.commit_hash

        assert hash1 != hash2

    def test_commit_hash_same_content_different_hash(self):
        """Test same content at different times has different hash."""
        sl1 = ScenarioList([Scenario({"a": 1})])
        sl2 = ScenarioList([Scenario({"a": 1})])

        # Different repo_ids mean different hashes even for same content
        # This is expected behavior
        assert sl1.commit_hash != sl2.commit_hash


class TestBranchName:
    """Tests for branch_name property."""

    def test_branch_name_default(self):
        """Test default branch name is 'main'."""
        sl = ScenarioList([Scenario({"a": 1})])

        assert sl.branch_name == "main"

    def test_branch_name_after_branch(self):
        """Test branch_name after creating branch."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl.git_branch("feature")

        assert sl.branch_name == "feature"

    def test_branch_name_none_when_detached(self):
        """Test branch_name is None in detached HEAD."""
        sl = ScenarioList([Scenario({"a": 1})])
        commit_hash = sl.commit_hash

        sl = sl.append(Scenario({"a": 2}))
        sl.git_commit("second")

        sl.git_checkout(commit_hash)

        assert sl.branch_name is None
