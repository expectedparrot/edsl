from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional


@dataclass
class QuestionSpec:
    """Normalized question specification for YAML serialization."""

    question_name: str
    question_text: str
    question_type: str
    question_options: Optional[List[Any]] = None
    derived_hints: Dict[str, Any] = field(default_factory=dict)

    def to_mapping(self) -> Dict[str, Any]:
        """Return a serializable mapping representation."""
        data: Dict[str, Any] = {
            "question_name": self.question_name,
            "question_text": self.question_text,
            "question_type": self.question_type,
        }
        if self.question_options is not None:
            data["question_options"] = list(self.question_options)
        if self.derived_hints:
            data["derived_hints"] = dict(self.derived_hints)
        return data


@dataclass
class AgentResponseRecord:
    """Long-format agent response record."""

    respondent_id: str
    question_name: str
    response: Any
    response_kind: str
    response_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_mapping(self) -> Dict[str, Any]:
        """Return a serializable mapping representation."""
        data: Dict[str, Any] = {
            "respondent_id": self.respondent_id,
            "question_name": self.question_name,
            "response": self.response,
            "response_kind": self.response_kind,
        }
        if self.response_metadata:
            data["response_metadata"] = dict(self.response_metadata)
        return data


@dataclass
class NormalizedSurvey:
    """Container for a normalized survey."""

    questions: List[QuestionSpec]
    responses: List[AgentResponseRecord]
    respondent_order: List[str]
    source_metadata: Dict[str, Any] = field(default_factory=dict)

    def iter_question_mappings(self) -> Iterable[Dict[str, Any]]:
        for question in self.questions:
            yield question.to_mapping()

    def iter_response_mappings(self) -> Iterable[Dict[str, Any]]:
        for response in self.responses:
            yield response.to_mapping()
