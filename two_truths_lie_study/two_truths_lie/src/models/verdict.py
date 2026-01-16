"""Verdict data model."""

from dataclasses import dataclass, field, asdict
import json


@dataclass(frozen=True)
class Verdict:
    """Represents the judge's final verdict.

    Attributes:
        judge_model: Model name of the judge
        accused_id: ID of the storyteller the judge believes is lying
        confidence: Judge's confidence level (1-10)
        reasoning: Judge's explanation for their choice
        frame_break_attempted: Whether judge tried to break the game frame
        raw_response: The full raw response from the LLM
    """

    judge_model: str
    accused_id: str
    confidence: int
    reasoning: str
    frame_break_attempted: bool = False
    raw_response: str = ""

    def __post_init__(self):
        if not 1 <= self.confidence <= 10:
            raise ValueError(f"Confidence must be 1-10, got {self.confidence}")

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict) -> "Verdict":
        """Create from dictionary."""
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> "Verdict":
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
