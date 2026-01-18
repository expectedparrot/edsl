"""Result storage and persistence for experimental rounds.

This module provides JSON-based storage for rounds with indexing and querying.
"""

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, List, Dict, Any
import json
from datetime import datetime

from .models import Round


@dataclass
class RoundFilters:
    """Filters for querying rounds.

    All filters are optional. Multiple filters are combined with AND logic.
    """

    judge_model: Optional[str] = None
    storyteller_model: Optional[str] = None
    strategy: Optional[str] = None
    question_style: Optional[str] = None
    category: Optional[str] = None
    detection_correct: Optional[bool] = None
    min_confidence: Optional[int] = None
    max_confidence: Optional[int] = None
    condition_id: Optional[str] = None


@dataclass
class ExperimentSummary:
    """Aggregate statistics for an experiment."""

    total_rounds: int
    judge_accuracy: float
    fibber_success_rate: float
    avg_confidence: float
    rounds_by_model: Dict[str, int]
    rounds_by_strategy: Dict[str, int]
    rounds_by_category: Dict[str, int]
    detection_by_confidence: Dict[int, float]  # confidence level -> accuracy


class ResultStore:
    """Persistent JSON-based storage for experimental rounds.

    Storage Structure:
        results/
        ├── index.json           # Round metadata for fast queries
        └── rounds/
            ├── <round_id>.json
            ├── <round_id>.json
            └── ...

    The index file contains minimal metadata for each round to enable
    fast filtering without loading all round files.
    """

    def __init__(self, base_dir: str = "results"):
        """Initialize the result store.

        Args:
            base_dir: Base directory for storing results
        """
        self.base_dir = Path(base_dir)
        self.rounds_dir = self.base_dir / "rounds"
        self.index_path = self.base_dir / "index.json"

        # Create directories
        self.rounds_dir.mkdir(parents=True, exist_ok=True)

        # Load or create index
        self._load_index()

    def _load_index(self) -> None:
        """Load the index from disk or create empty index."""
        if self.index_path.exists():
            with open(self.index_path, 'r') as f:
                self.index = json.load(f)
        else:
            self.index = {
                "rounds": {},  # round_id -> metadata
                "last_updated": datetime.now().isoformat()
            }
            self._save_index()

    def _save_index(self) -> None:
        """Save the index to disk."""
        self.index["last_updated"] = datetime.now().isoformat()
        with open(self.index_path, 'w') as f:
            json.dump(self.index, f, indent=2)

    def _extract_metadata(self, round_obj: Round) -> Dict[str, Any]:
        """Extract searchable metadata from a round.

        Args:
            round_obj: Round object

        Returns:
            Dictionary of metadata for indexing
        """
        return {
            "round_id": round_obj.round_id,
            "judge_model": round_obj.setup.judge.model,
            "storyteller_model": round_obj.setup.storytellers[0].model,
            "strategy": round_obj.setup.storytellers[0].strategy,
            "question_style": round_obj.setup.judge.question_style,
            "category": round_obj.setup.fact_category,
            "condition_id": round_obj.setup.condition_id,
            "detection_correct": round_obj.outcome.detection_correct,
            "confidence": round_obj.verdict.confidence,
            "fibber_id": round_obj.outcome.fibber_id,
            "accused_id": round_obj.outcome.accused_id,
            "duration_seconds": round_obj.duration_seconds,
            "timestamp": datetime.now().isoformat()
        }

    def save_round(self, round_obj: Round) -> None:
        """Save a completed round.

        Args:
            round_obj: Completed round to save
        """
        # Save full round data
        round_path = self.rounds_dir / f"{round_obj.round_id}.json"
        with open(round_path, 'w') as f:
            f.write(round_obj.to_json())

        # Update index with metadata
        metadata = self._extract_metadata(round_obj)
        self.index["rounds"][round_obj.round_id] = metadata
        self._save_index()

    def get_round(self, round_id: str) -> Round:
        """Retrieve a round by ID.

        Args:
            round_id: ID of the round to retrieve

        Returns:
            Round object

        Raises:
            FileNotFoundError: If round doesn't exist
        """
        round_path = self.rounds_dir / f"{round_id}.json"
        if not round_path.exists():
            raise FileNotFoundError(f"Round {round_id} not found")

        with open(round_path, 'r') as f:
            return Round.from_json(f.read())

    def round_exists(self, round_id: str) -> bool:
        """Check if a round exists.

        Args:
            round_id: ID to check

        Returns:
            True if round exists
        """
        return round_id in self.index["rounds"]

    def list_rounds(self) -> List[str]:
        """Get list of all round IDs.

        Returns:
            List of round IDs
        """
        return list(self.index["rounds"].keys())

    def _matches_filters(self, metadata: Dict[str, Any], filters: RoundFilters) -> bool:
        """Check if round metadata matches filters.

        Args:
            metadata: Round metadata from index
            filters: Filters to apply

        Returns:
            True if metadata matches all filters
        """
        if filters.judge_model and metadata["judge_model"] != filters.judge_model:
            return False
        if filters.storyteller_model and metadata["storyteller_model"] != filters.storyteller_model:
            return False
        if filters.strategy and metadata["strategy"] != filters.strategy:
            return False
        if filters.question_style and metadata["question_style"] != filters.question_style:
            return False
        if filters.category and metadata["category"] != filters.category:
            return False
        if filters.detection_correct is not None and metadata["detection_correct"] != filters.detection_correct:
            return False
        if filters.min_confidence is not None and metadata["confidence"] < filters.min_confidence:
            return False
        if filters.max_confidence is not None and metadata["confidence"] > filters.max_confidence:
            return False

        return True

    def query_rounds(self, filters: RoundFilters) -> List[Round]:
        """Query rounds with filters.

        Args:
            filters: Filters to apply

        Returns:
            List of rounds matching filters
        """
        matching_ids = [
            round_id
            for round_id, metadata in self.index["rounds"].items()
            if self._matches_filters(metadata, filters)
        ]

        return [self.get_round(rid) for rid in matching_ids]

    def get_summary(self) -> ExperimentSummary:
        """Generate aggregate statistics.

        Returns:
            ExperimentSummary with aggregate metrics
        """
        if not self.index["rounds"]:
            return ExperimentSummary(
                total_rounds=0,
                judge_accuracy=0.0,
                fibber_success_rate=0.0,
                avg_confidence=0.0,
                rounds_by_model={},
                rounds_by_strategy={},
                rounds_by_category={},
                detection_by_confidence={}
            )

        rounds = list(self.index["rounds"].values())
        total = len(rounds)

        # Judge accuracy
        correct = sum(1 for r in rounds if r["detection_correct"])
        judge_accuracy = correct / total if total > 0 else 0.0

        # Fibber success (inverse of detection)
        fibber_success_rate = 1.0 - judge_accuracy

        # Average confidence
        avg_confidence = sum(r["confidence"] for r in rounds) / total

        # Counts by dimension
        rounds_by_model = {}
        rounds_by_strategy = {}
        rounds_by_category = {}

        for r in rounds:
            model = r["judge_model"]
            rounds_by_model[model] = rounds_by_model.get(model, 0) + 1

            strategy = r["strategy"]
            rounds_by_strategy[strategy] = rounds_by_strategy.get(strategy, 0) + 1

            category = r["category"]
            rounds_by_category[category] = rounds_by_category.get(category, 0) + 1

        # Detection accuracy by confidence level
        detection_by_confidence = {}
        for conf_level in range(1, 11):
            at_level = [r for r in rounds if r["confidence"] == conf_level]
            if at_level:
                accuracy = sum(1 for r in at_level if r["detection_correct"]) / len(at_level)
                detection_by_confidence[conf_level] = accuracy

        return ExperimentSummary(
            total_rounds=total,
            judge_accuracy=judge_accuracy,
            fibber_success_rate=fibber_success_rate,
            avg_confidence=avg_confidence,
            rounds_by_model=rounds_by_model,
            rounds_by_strategy=rounds_by_strategy,
            rounds_by_category=rounds_by_category,
            detection_by_confidence=detection_by_confidence
        )

    def delete_round(self, round_id: str) -> None:
        """Delete a round.

        Args:
            round_id: ID of round to delete
        """
        # Remove file
        round_path = self.rounds_dir / f"{round_id}.json"
        if round_path.exists():
            round_path.unlink()

        # Remove from index
        if round_id in self.index["rounds"]:
            del self.index["rounds"][round_id]
            self._save_index()

    def clear_all(self) -> None:
        """Delete all rounds. Use with caution!"""
        # Delete all round files
        for round_file in self.rounds_dir.glob("*.json"):
            round_file.unlink()

        # Reset index
        self.index = {
            "rounds": {},
            "last_updated": datetime.now().isoformat()
        }
        self._save_index()
