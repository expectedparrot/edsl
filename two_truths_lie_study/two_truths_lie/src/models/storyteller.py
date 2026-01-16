"""Storyteller and Judge data models."""

from dataclasses import dataclass, field, asdict
from typing import Literal, Optional
import json


@dataclass(frozen=True)
class Storyteller:
    """Represents a storyteller in the game.

    Attributes:
        id: Unique identifier (A, B, C, etc.)
        model: Name of the LLM model
        role: Whether this storyteller is telling truth or lying
        strategy: The storytelling strategy being used
        fact_id: For truth-tellers, the ID of their assigned fact
    """

    id: str  # "A", "B", "C"
    model: str
    role: Literal["truth_teller", "fibber"]
    strategy: str = "baseline"
    fact_id: Optional[str] = None

    def __post_init__(self):
        if self.role == "truth_teller" and self.fact_id is None:
            raise ValueError("Truth-tellers must have a fact_id")
        if self.role == "fibber" and self.fact_id is not None:
            raise ValueError("Fibbers should not have a fact_id")

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict) -> "Storyteller":
        """Create from dictionary."""
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> "Storyteller":
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))

    @property
    def is_truth_teller(self) -> bool:
        """Check if this storyteller is telling the truth."""
        return self.role == "truth_teller"

    @property
    def is_fibber(self) -> bool:
        """Check if this storyteller is lying."""
        return self.role == "fibber"


@dataclass(frozen=True)
class Judge:
    """Represents a judge in the game.

    Attributes:
        model: Name of the LLM model
        temperature: Temperature setting for generation
        question_style: Style of questioning (adversarial, curious, etc.)
    """

    model: str
    temperature: float = 1.0
    question_style: str = "curious"

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict) -> "Judge":
        """Create from dictionary."""
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> "Judge":
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))
