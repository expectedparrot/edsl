"""Tests for result storage."""

import pytest
import tempfile
import shutil
from pathlib import Path

from src.storage import ResultStore, RoundFilters, ExperimentSummary
from src.models import Round
from tests.fixtures import create_mock_round


class TestResultStore:
    """Test suite for ResultStore."""

    @pytest.fixture
    def temp_store(self):
        """Create a temporary result store."""
        temp_dir = tempfile.mkdtemp()
        store = ResultStore(base_dir=temp_dir)
        yield store
        # Cleanup
        shutil.rmtree(temp_dir)

    def test_initialization(self, temp_store):
        """Test store initializes correctly."""
        assert temp_store.base_dir.exists()
        assert temp_store.rounds_dir.exists()
        assert temp_store.index_path.exists()
        assert temp_store.index["rounds"] == {}

    def test_save_and_retrieve_round(self, temp_store):
        """Test saving and retrieving a round."""
        round_obj = create_mock_round()

        # Save
        temp_store.save_round(round_obj)

        # Verify file exists
        round_path = temp_store.rounds_dir / f"{round_obj.round_id}.json"
        assert round_path.exists()

        # Retrieve
        retrieved = temp_store.get_round(round_obj.round_id)
        assert retrieved.round_id == round_obj.round_id
        assert retrieved.verdict.accused_id == round_obj.verdict.accused_id

    def test_round_exists(self, temp_store):
        """Test round_exists check."""
        round_obj = create_mock_round()

        assert not temp_store.round_exists(round_obj.round_id)

        temp_store.save_round(round_obj)

        assert temp_store.round_exists(round_obj.round_id)

    def test_list_rounds(self, temp_store):
        """Test listing all rounds."""
        assert temp_store.list_rounds() == []

        round1 = create_mock_round()
        round2 = create_mock_round()

        temp_store.save_round(round1)
        temp_store.save_round(round2)

        round_ids = temp_store.list_rounds()
        assert len(round_ids) == 2
        assert round1.round_id in round_ids
        assert round2.round_id in round_ids

    def test_query_by_model(self, temp_store):
        """Test querying by judge model."""
        # Create rounds with different models
        round1 = create_mock_round(judge_model="gpt-4o")
        round2 = create_mock_round(judge_model="claude-3-5-haiku-20241022")
        round3 = create_mock_round(judge_model="gpt-4o")

        temp_store.save_round(round1)
        temp_store.save_round(round2)
        temp_store.save_round(round3)

        # Query for gpt-4o
        filters = RoundFilters(judge_model="gpt-4o")
        results = temp_store.query_rounds(filters)

        assert len(results) == 2
        assert all(r.setup.judge.model == "gpt-4o" for r in results)

    def test_query_by_outcome(self, temp_store):
        """Test querying by detection outcome."""
        # Create rounds with different outcomes
        round1 = create_mock_round(detection_correct=True)
        round2 = create_mock_round(detection_correct=False)
        round3 = create_mock_round(detection_correct=True)

        temp_store.save_round(round1)
        temp_store.save_round(round2)
        temp_store.save_round(round3)

        # Query for correct detections
        filters = RoundFilters(detection_correct=True)
        results = temp_store.query_rounds(filters)

        assert len(results) == 2
        assert all(r.outcome.detection_correct for r in results)

    def test_query_by_confidence(self, temp_store):
        """Test querying by confidence range."""
        # Create rounds with different confidence levels
        round1 = create_mock_round(confidence=3)
        round2 = create_mock_round(confidence=7)
        round3 = create_mock_round(confidence=9)

        temp_store.save_round(round1)
        temp_store.save_round(round2)
        temp_store.save_round(round3)

        # Query for high confidence (>= 7)
        filters = RoundFilters(min_confidence=7)
        results = temp_store.query_rounds(filters)

        assert len(results) == 2
        assert all(r.verdict.confidence >= 7 for r in results)

    def test_query_multiple_filters(self, temp_store):
        """Test querying with multiple filters."""
        # Create diverse rounds
        round1 = create_mock_round(
            judge_model="gpt-4o",
            strategy="baseline",
            detection_correct=True
        )
        round2 = create_mock_round(
            judge_model="gpt-4o",
            strategy="verbose",
            detection_correct=True
        )
        round3 = create_mock_round(
            judge_model="claude-3-5-haiku-20241022",
            strategy="baseline",
            detection_correct=False
        )

        temp_store.save_round(round1)
        temp_store.save_round(round2)
        temp_store.save_round(round3)

        # Query for: gpt-4o AND baseline
        filters = RoundFilters(judge_model="gpt-4o", strategy="baseline")
        results = temp_store.query_rounds(filters)

        assert len(results) == 1
        assert results[0].round_id == round1.round_id

    def test_get_summary_empty(self, temp_store):
        """Test summary with no rounds."""
        summary = temp_store.get_summary()

        assert summary.total_rounds == 0
        assert summary.judge_accuracy == 0.0
        assert summary.rounds_by_model == {}

    def test_get_summary_with_rounds(self, temp_store):
        """Test summary with rounds."""
        # Create 10 rounds: 7 correct, 3 incorrect
        for i in range(7):
            temp_store.save_round(create_mock_round(detection_correct=True))

        for i in range(3):
            temp_store.save_round(create_mock_round(detection_correct=False))

        summary = temp_store.get_summary()

        assert summary.total_rounds == 10
        assert summary.judge_accuracy == pytest.approx(0.7)
        assert summary.fibber_success_rate == pytest.approx(0.3)

    def test_delete_round(self, temp_store):
        """Test deleting a round."""
        round_obj = create_mock_round()
        temp_store.save_round(round_obj)

        assert temp_store.round_exists(round_obj.round_id)

        temp_store.delete_round(round_obj.round_id)

        assert not temp_store.round_exists(round_obj.round_id)
        assert round_obj.round_id not in temp_store.list_rounds()

    def test_clear_all(self, temp_store):
        """Test clearing all rounds."""
        # Add multiple rounds
        for i in range(5):
            temp_store.save_round(create_mock_round())

        assert len(temp_store.list_rounds()) == 5

        # Clear all
        temp_store.clear_all()

        assert len(temp_store.list_rounds()) == 0
        assert temp_store.index["rounds"] == {}

    def test_index_persistence(self, temp_store):
        """Test that index persists across store instances."""
        round_obj = create_mock_round()
        temp_store.save_round(round_obj)

        # Create new store instance pointing to same directory
        new_store = ResultStore(base_dir=str(temp_store.base_dir))

        # Should still have the round
        assert new_store.round_exists(round_obj.round_id)
        retrieved = new_store.get_round(round_obj.round_id)
        assert retrieved.round_id == round_obj.round_id

    def test_metadata_extraction(self, temp_store):
        """Test metadata extraction is accurate."""
        round_obj = create_mock_round(
            judge_model="test-model",
            strategy="test-strategy",
            confidence=8,
            detection_correct=True
        )

        metadata = temp_store._extract_metadata(round_obj)

        assert metadata["judge_model"] == "test-model"
        assert metadata["strategy"] == "test-strategy"
        assert metadata["confidence"] == 8
        assert metadata["detection_correct"] is True
        assert "round_id" in metadata
        assert "timestamp" in metadata
