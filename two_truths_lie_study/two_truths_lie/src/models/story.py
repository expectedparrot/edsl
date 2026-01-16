"""Story data model."""

from dataclasses import dataclass, field, asdict
from typing import Optional
import json


@dataclass(frozen=True)
class Story:
    """Represents a story told by a storyteller.

    Attributes:
        storyteller_id: ID of the storyteller who told this story
        content: The full text of the story
        source_cited: Any source mentioned in the story
        word_count: Number of words in the story
        generation_metadata: Metadata from generation (tokens, latency, etc.)
    """

    storyteller_id: str
    content: str
    word_count: int
    source_cited: Optional[str] = None
    generation_metadata: dict = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        storyteller_id: str,
        content: str,
        source_cited: Optional[str] = None,
        generation_metadata: Optional[dict] = None
    ) -> "Story":
        """Factory method to create a Story with computed word count."""
        word_count = len(content.split())
        return cls(
            storyteller_id=storyteller_id,
            content=content,
            word_count=word_count,
            source_cited=source_cited,
            generation_metadata=generation_metadata or {}
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict) -> "Story":
        """Create from dictionary."""
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> "Story":
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))

    def get_preview(self, max_words: int = 50) -> str:
        """Get a preview of the story."""
        words = self.content.split()
        if len(words) <= max_words:
            return self.content
        return " ".join(words[:max_words]) + "..."
