from dataclasses import dataclass
from typing import Any

from .exceptions import SharedStateResolutionError


@dataclass(frozen=True)
class AnswerRef:
    question_name: str

    def resolve(self, answers: dict) -> Any:
        if self.question_name not in answers:
            raise SharedStateResolutionError(
                f"answer for question '{self.question_name}' is not available; "
                "place the write step after that question"
            )
        return answers[self.question_name]

    def to_dict(self) -> dict:
        return {"question_name": self.question_name}

    @classmethod
    def from_dict(cls, data: dict) -> "AnswerRef":
        return cls(data["question_name"])
