"""Question and Answer data models."""

from dataclasses import dataclass, field, asdict
from typing import Optional
import json


@dataclass(frozen=True)
class Question:
    """Represents a question asked by the judge.

    Attributes:
        judge_model: Model name of the judge asking the question
        target_storyteller_id: ID of the storyteller being asked
        content: The question text
        question_number: Which question this is (1, 2, 3, etc.)
        generation_metadata: Metadata from generation
    """

    judge_model: str
    target_storyteller_id: str
    content: str
    question_number: int
    generation_metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict) -> "Question":
        """Create from dictionary."""
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> "Question":
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))


@dataclass(frozen=True)
class Answer:
    """Represents an answer from a storyteller.

    Attributes:
        storyteller_id: ID of the storyteller answering
        question_number: Which question this answers
        content: The answer text
        word_count: Number of words in the answer
        generation_metadata: Metadata from generation
    """

    storyteller_id: str
    question_number: int
    content: str
    word_count: int
    generation_metadata: dict = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        storyteller_id: str,
        question_number: int,
        content: str,
        generation_metadata: Optional[dict] = None
    ) -> "Answer":
        """Factory method to create an Answer with computed word count."""
        word_count = len(content.split())
        return cls(
            storyteller_id=storyteller_id,
            question_number=question_number,
            content=content,
            word_count=word_count,
            generation_metadata=generation_metadata or {}
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict) -> "Answer":
        """Create from dictionary."""
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> "Answer":
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))


@dataclass(frozen=True)
class QAExchange:
    """Represents a complete question-answer exchange.

    Attributes:
        question: The question asked
        answer: The answer given
    """

    question: Question
    answer: Answer

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "question": self.question.to_dict(),
            "answer": self.answer.to_dict()
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict) -> "QAExchange":
        """Create from dictionary."""
        return cls(
            question=Question.from_dict(data["question"]),
            answer=Answer.from_dict(data["answer"])
        )

    @classmethod
    def from_json(cls, json_str: str) -> "QAExchange":
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))
