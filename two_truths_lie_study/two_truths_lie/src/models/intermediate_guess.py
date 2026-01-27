"""Intermediate guess data model."""

from dataclasses import dataclass, asdict
import json


@dataclass(frozen=True)
class IntermediateGuess:
    """Represents the judge's guess after a Q&A exchange.

    This allows tracking of one-shot, two-shot, n-shot performance
    as the judge gathers more information.

    Attributes:
        judge_model: Model name of the judge
        after_qa_number: Which Q&A exchange this guess comes after (1-indexed)
        accused_id: ID of the storyteller the judge believes is lying
        confidence: Judge's confidence level (1-10)
        reasoning: Optional brief explanation
        raw_response: The full raw response from the LLM
    """

    judge_model: str
    after_qa_number: int  # Cumulative Q&A count
    accused_id: str
    confidence: int
    reasoning: str = ""
    raw_response: str = ""

    def __post_init__(self):
        if not 1 <= self.confidence <= 10:
            raise ValueError(f"Confidence must be 1-10, got {self.confidence}")
        if self.after_qa_number < 1:
            raise ValueError(f"after_qa_number must be >= 1, got {self.after_qa_number}")

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict) -> "IntermediateGuess":
        """Create from dictionary."""
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> "IntermediateGuess":
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))

    @property
    def is_high_confidence(self) -> bool:
        """Check if the judge is highly confident (>= 7)."""
        return self.confidence >= 7

    @property
    def is_low_confidence(self) -> bool:
        """Check if the judge has low confidence (<= 3)."""
        return self.confidence <= 3
