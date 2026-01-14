"""Tests for versioning storage layer (InMemoryRepo serialization)."""

import pytest
from datetime import datetime

from edsl.versioning.storage import (
    InMemoryRepo,
    _commit_to_dict,
    _commit_from_dict,
    _ref_to_dict,
    _ref_from_dict,
)
from edsl.versioning.models import Commit, Ref


class TestCommitSerialization:
    """Tests for Commit serialization helpers."""

    def test_commit_round_trip(self):
        """Test Commit serializes and deserializes correctly."""
        commit = Commit(
            commit_id="abc123",
            parents=("parent1", "parent2"),
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            message="test commit",
            event_name="test_event",
            event_payload={"key": "value", "nested": {"a": 1}},
            author="test_author",
        )

        d = _commit_to_dict(commit)
        restored = _commit_from_dict(d)

        assert restored.commit_id == commit.commit_id
        assert restored.parents == commit.parents
        assert restored.timestamp == commit.timestamp
        assert restored.message == commit.message
        assert restored.event_name == commit.event_name
        assert restored.event_payload == commit.event_payload
        assert restored.author == commit.author

    def test_commit_to_dict_format(self):
        """Test _commit_to_dict produces correct format."""
        commit = Commit(
            commit_id="abc123",
            parents=("parent1",),
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            message="test",
            event_name="event",
            event_payload={},
            author="author",
        )

        d = _commit_to_dict(commit)

        assert d["commit_id"] == "abc123"
        assert d["parents"] == ["parent1"]
        assert d["timestamp"] == "2024-01-15T10:30:00"
        assert d["message"] == "test"
        assert d["event_name"] == "event"
        assert d["event_payload"] == {}
        assert d["author"] == "author"

    def test_commit_default_author(self):
        """Test default author when missing from dict."""
        d = {
            "commit_id": "abc123",
            "parents": [],
            "timestamp": "2024-01-15T10:30:00",
            "message": "test",
            "event_name": "event",
            "event_payload": {},
        }

        commit = _commit_from_dict(d)

        assert commit.author == "unknown"


class TestRefSerialization:
    """Tests for Ref serialization helpers."""

    def test_ref_round_trip(self):
        """Test Ref serializes and deserializes correctly."""
        ref = Ref(
            name="main",
            commit_id="abc123",
            kind="branch",
            updated_at=datetime(2024, 1, 15, 10, 30, 0),
        )

        d = _ref_to_dict(ref)
        restored = _ref_from_dict(d)

        assert restored.name == ref.name
        assert restored.commit_id == ref.commit_id
        assert restored.kind == ref.kind
        assert restored.updated_at == ref.updated_at

    def test_ref_to_dict_format(self):
        """Test _ref_to_dict produces correct format."""
        ref = Ref(
            name="feature",
            commit_id="def456",
            kind="branch",
            updated_at=datetime(2024, 1, 15, 10, 30, 0),
        )

        d = _ref_to_dict(ref)

        assert d["name"] == "feature"
        assert d["commit_id"] == "def456"
        assert d["kind"] == "branch"
        assert d["updated_at"] == "2024-01-15T10:30:00"

    def test_ref_default_kind(self):
        """Test default kind when missing from dict."""
        d = {
            "name": "main",
            "commit_id": "abc123",
            "updated_at": "2024-01-15T10:30:00",
        }

        ref = _ref_from_dict(d)

        assert ref.kind == "branch"


class TestInMemoryRepoSerialization:
    """Tests for InMemoryRepo to_dict/from_dict."""

    def test_empty_repo_round_trip(self):
        """Test empty repo serializes and deserializes."""
        repo = InMemoryRepo()

        d = repo.to_dict()
        restored = InMemoryRepo.from_dict(d)

        assert restored.repo_id == repo.repo_id
        assert restored._states == {}
        assert restored._commits == {}
        assert restored._refs == {}

    def test_repo_with_state_round_trip(self):
        """Test repo with state data round trips correctly."""
        repo = InMemoryRepo()
        state_data = [{"entries": [{"a": 1}], "meta": {}}]
        state_id = repo.put_state(state_data)

        d = repo.to_dict()
        restored = InMemoryRepo.from_dict(d)

        assert restored.has_state(state_id)
        restored_state = restored.get_state(state_id)
        assert restored_state == state_data

    def test_repo_with_commits_round_trip(self):
        """Test repo with commits round trips correctly."""
        repo = InMemoryRepo()

        commit = Commit(
            commit_id="abc123",
            parents=(),
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            message="test",
            event_name="init",
            event_payload={},
            author="test",
        )
        repo.put_commit(commit, state_id=None)

        d = repo.to_dict()
        restored = InMemoryRepo.from_dict(d)

        assert restored.has_commit("abc123")
        restored_commit = restored.get_commit("abc123")
        assert restored_commit.message == "test"

    def test_repo_with_refs_round_trip(self):
        """Test repo with refs round trips correctly."""
        repo = InMemoryRepo()

        commit = Commit(
            commit_id="abc123",
            parents=(),
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            message="test",
            event_name="init",
            event_payload={},
            author="test",
        )
        repo.put_commit(commit)
        repo.upsert_ref("main", "abc123", kind="branch")
        repo.upsert_ref("v1.0", "abc123", kind="tag")

        d = repo.to_dict()
        restored = InMemoryRepo.from_dict(d)

        assert restored.has_ref("main")
        assert restored.has_ref("v1.0")
        assert restored.get_ref("main").kind == "branch"
        assert restored.get_ref("v1.0").kind == "tag"

    def test_repo_with_commit_state_mapping(self):
        """Test commit to state mapping is preserved."""
        repo = InMemoryRepo()

        state_data = [{"entries": [{"x": 1}], "meta": {}}]
        state_id = repo.put_state(state_data)

        commit = Commit(
            commit_id="abc123",
            parents=(),
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            message="test",
            event_name="init",
            event_payload={},
            author="test",
        )
        repo.put_commit(commit, state_id=state_id)

        d = repo.to_dict()
        restored = InMemoryRepo.from_dict(d)

        assert restored.get_commit_state_id("abc123") == state_id

    def test_repo_preserves_repo_id(self):
        """Test repo_id is preserved through serialization."""
        repo = InMemoryRepo()
        original_id = repo.repo_id

        d = repo.to_dict()
        restored = InMemoryRepo.from_dict(d)

        assert restored.repo_id == original_id

    def test_repo_to_dict_structure(self):
        """Test to_dict produces correct structure."""
        repo = InMemoryRepo()

        d = repo.to_dict()

        assert "repo_id" in d
        assert "states" in d
        assert "commits" in d
        assert "commit_to_state" in d
        assert "refs" in d

        assert isinstance(d["states"], dict)
        assert isinstance(d["commits"], dict)
        assert isinstance(d["commit_to_state"], dict)
        assert isinstance(d["refs"], dict)


class TestComplexScenarios:
    """Tests for complex serialization scenarios."""

    def test_multiple_branches(self):
        """Test repo with multiple branches serializes correctly."""
        repo = InMemoryRepo()

        # Create commits
        for i, name in enumerate(["main", "feature", "hotfix"]):
            commit = Commit(
                commit_id=f"commit{i}",
                parents=(),
                timestamp=datetime(2024, 1, 15, 10, 30, i),
                message=f"{name} commit",
                event_name="init",
                event_payload={},
                author="test",
            )
            repo.put_commit(commit)
            repo.upsert_ref(name, f"commit{i}", kind="branch")

        d = repo.to_dict()
        restored = InMemoryRepo.from_dict(d)

        refs = restored.list_refs()
        ref_names = {r.name for r in refs}

        assert ref_names == {"main", "feature", "hotfix"}

    def test_unicode_in_state(self):
        """Test unicode data in state is preserved."""
        repo = InMemoryRepo()

        state_data = [
            {
                "entries": [{"emoji": "🎉", "chinese": "你好"}],
                "meta": {"description": "测试"},
            }
        ]
        state_id = repo.put_state(state_data)

        d = repo.to_dict()
        restored = InMemoryRepo.from_dict(d)

        restored_state = restored.get_state(state_id)
        assert restored_state[0]["entries"][0]["emoji"] == "🎉"
        assert restored_state[0]["entries"][0]["chinese"] == "你好"
        assert restored_state[0]["meta"]["description"] == "测试"

    def test_large_payload(self):
        """Test commit with large event payload."""
        repo = InMemoryRepo()

        large_payload = {
            "data": list(range(1000)),
            "nested": {f"key{i}": f"value{i}" for i in range(100)},
        }

        commit = Commit(
            commit_id="abc123",
            parents=(),
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            message="large",
            event_name="big_event",
            event_payload=large_payload,
            author="test",
        )
        repo.put_commit(commit)

        d = repo.to_dict()
        restored = InMemoryRepo.from_dict(d)

        restored_commit = restored.get_commit("abc123")
        assert restored_commit.event_payload == large_payload
