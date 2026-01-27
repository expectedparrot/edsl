"""Round data models."""

from dataclasses import dataclass, field, asdict
from typing import List, Optional
from datetime import datetime
import json
import uuid

from .storyteller import Storyteller, Judge
from .story import Story
from .qa import QAExchange
from .verdict import Verdict
from .intermediate_guess import IntermediateGuess


@dataclass
class RoundSetup:
    """Configuration for a round before execution.

    Attributes:
        round_id: Unique identifier for this round
        storytellers: List of storytellers with assigned roles
        judge: The judge for this round
        story_order: Randomized order for presenting stories to judge
        fact_category: Category of facts being used
        condition_id: ID of the experimental condition
    """

    round_id: str
    storytellers: List[Storyteller]
    judge: Judge
    story_order: List[str]  # Randomized order of storyteller IDs
    fact_category: str
    condition_id: Optional[str] = None

    @classmethod
    def create(
        cls,
        storytellers: List[Storyteller],
        judge: Judge,
        fact_category: str,
        condition_id: Optional[str] = None
    ) -> "RoundSetup":
        """Factory method to create a RoundSetup with generated ID and randomized order."""
        import random

        round_id = str(uuid.uuid4())[:8]
        story_order = [s.id for s in storytellers]
        random.shuffle(story_order)

        return cls(
            round_id=round_id,
            storytellers=storytellers,
            judge=judge,
            story_order=story_order,
            fact_category=fact_category,
            condition_id=condition_id
        )

    def get_fibber(self) -> Optional[Storyteller]:
        """Get the fibber storyteller (if any)."""
        for s in self.storytellers:
            if s.is_fibber:
                return s
        return None

    def get_truth_tellers(self) -> List[Storyteller]:
        """Get all truth-telling storytellers."""
        return [s for s in self.storytellers if s.is_truth_teller]

    def get_storyteller(self, storyteller_id: str) -> Optional[Storyteller]:
        """Get a storyteller by ID."""
        for s in self.storytellers:
            if s.id == storyteller_id:
                return s
        return None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "round_id": self.round_id,
            "storytellers": [s.to_dict() for s in self.storytellers],
            "judge": self.judge.to_dict(),
            "story_order": self.story_order,
            "fact_category": self.fact_category,
            "condition_id": self.condition_id
        }


@dataclass(frozen=True)
class RoundOutcome:
    """Outcome metrics for a completed round.

    Attributes:
        detection_correct: Whether the judge correctly identified the fibber
        false_accusation: Whether the judge accused a truth-teller
        fibber_id: ID of the actual fibber (if any)
        accused_id: ID of who the judge accused
        confidence: Judge's confidence level
    """

    detection_correct: bool
    false_accusation: bool
    fibber_id: Optional[str]  # None for all_truth config
    accused_id: str
    confidence: int

    @classmethod
    def calculate(
        cls,
        setup: RoundSetup,
        verdict: Verdict
    ) -> "RoundOutcome":
        """Calculate the outcome based on setup and verdict."""
        fibber = setup.get_fibber()
        fibber_id = fibber.id if fibber else None

        # Determine if detection was correct
        if fibber_id is None:
            # No fibber (all_truth config): any accusation is wrong
            detection_correct = False
            false_accusation = True
        else:
            detection_correct = verdict.accused_id == fibber_id
            false_accusation = verdict.accused_id != fibber_id

        return cls(
            detection_correct=detection_correct,
            false_accusation=false_accusation,
            fibber_id=fibber_id,
            accused_id=verdict.accused_id,
            confidence=verdict.confidence
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return asdict(self)


@dataclass
class Round:
    """Complete data for a single game round.

    Attributes:
        setup: The round configuration
        stories: Generated stories
        qa_exchanges: All Q&A exchanges
        intermediate_guesses: Judge's guesses after each Q&A (for n-shot analysis)
        verdict: Judge's final verdict
        outcome: Calculated outcome
        timestamp: When the round was completed
        duration_seconds: How long the round took
    """

    setup: RoundSetup
    stories: List[Story]
    qa_exchanges: List[QAExchange]
    intermediate_guesses: List[IntermediateGuess]
    verdict: Verdict
    outcome: RoundOutcome
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    duration_seconds: Optional[float] = None

    @property
    def round_id(self) -> str:
        """Get the round ID."""
        return self.setup.round_id

    def get_story_for_storyteller(self, storyteller_id: str) -> Optional[Story]:
        """Get the story for a specific storyteller."""
        for story in self.stories:
            if story.storyteller_id == storyteller_id:
                return story
        return None

    def get_qa_for_storyteller(self, storyteller_id: str) -> List[QAExchange]:
        """Get all Q&A exchanges for a specific storyteller."""
        return [
            qa for qa in self.qa_exchanges
            if qa.question.target_storyteller_id == storyteller_id
        ]

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "setup": self.setup.to_dict(),
            "stories": [s.to_dict() for s in self.stories],
            "qa_exchanges": [qa.to_dict() for qa in self.qa_exchanges],
            "intermediate_guesses": [ig.to_dict() for ig in self.intermediate_guesses],
            "verdict": self.verdict.to_dict(),
            "outcome": self.outcome.to_dict(),
            "timestamp": self.timestamp,
            "duration_seconds": self.duration_seconds
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> "Round":
        """Create from dictionary."""
        setup_data = data["setup"]
        setup = RoundSetup(
            round_id=setup_data["round_id"],
            storytellers=[Storyteller.from_dict(s) for s in setup_data["storytellers"]],
            judge=Judge.from_dict(setup_data["judge"]),
            story_order=setup_data["story_order"],
            fact_category=setup_data["fact_category"],
            condition_id=setup_data.get("condition_id")
        )

        stories = [Story.from_dict(s) for s in data["stories"]]
        qa_exchanges = [QAExchange.from_dict(qa) for qa in data["qa_exchanges"]]
        intermediate_guesses = [IntermediateGuess.from_dict(ig) for ig in data.get("intermediate_guesses", [])]
        verdict = Verdict.from_dict(data["verdict"])
        outcome = RoundOutcome(**data["outcome"])

        return cls(
            setup=setup,
            stories=stories,
            qa_exchanges=qa_exchanges,
            intermediate_guesses=intermediate_guesses,
            verdict=verdict,
            outcome=outcome,
            timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
            duration_seconds=data.get("duration_seconds")
        )

    @classmethod
    def from_json(cls, json_str: str) -> "Round":
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))
