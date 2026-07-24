from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, field_validator

from .decorators import inject_exception
from .question_base import QuestionBase
from .response_validator_abc import ResponseValidatorABC


class SlopResponse(BaseModel):
    answer: dict[str, Any]
    generated_tokens: Optional[str] = None
    comment: Optional[str] = None

    @field_validator("answer")
    @classmethod
    def validate_answer(cls, value):
        if not isinstance(value, dict):
            raise ValueError("answer must be a dictionary")
        return value


class SlopResponseValidator(ResponseValidatorABC):
    required_params = []
    valid_examples = [
        (
            {
                "answer": {
                    "classification": "human",
                    "ai_score": 0.0,
                    "human_score": 1.0,
                    "provider": "pangram",
                }
            },
            {},
        )
    ]
    invalid_examples = []


class QuestionSlop(QuestionBase):
    """A question that scores text with an AI-text detector provider.

    The MVP provider is Pangram. The question renders ``question_text`` using
    normal EDSL scenario/prior-answer variables, sends only that rendered text
    to the provider, and returns normalized detector metrics as a dict answer.

    Examples:
        >>> q = QuestionSlop(question_name="slop", question_text="{{ text }}")
        >>> q.question_type
        'slop'
    """

    question_type = "slop"
    _response_model = SlopResponse
    response_validator_class = SlopResponseValidator

    def __init__(
        self,
        question_name: str,
        question_text: str,
        provider: str = "pangram",
        include_segments: bool = True,
        include_raw_response: bool = False,
        public_dashboard_link: bool = False,
        min_text_length: int = 0,
        on_short_text: str = "return_null",
        timeout_seconds: float = 300,
        poll_interval: float = 0.5,
        answering_instructions: Optional[str] = None,
        question_presentation: Optional[str] = None,
    ):
        if provider != "pangram":
            raise ValueError("QuestionSlop currently supports only provider='pangram'")
        if on_short_text not in {"return_null", "score_anyway", "raise"}:
            raise ValueError(
                "on_short_text must be 'return_null', 'score_anyway', or 'raise'"
            )
        if min_text_length < 0:
            raise ValueError("min_text_length must be non-negative")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")

        self.question_name = question_name
        self.question_text = question_text
        self.provider = provider
        self.include_segments = include_segments
        self.include_raw_response = include_raw_response
        self.public_dashboard_link = public_dashboard_link
        self.min_text_length = min_text_length
        self.on_short_text = on_short_text
        self.timeout_seconds = timeout_seconds
        self.poll_interval = poll_interval
        self.answering_instructions = answering_instructions
        self.question_presentation = question_presentation

    @property
    def _invigilator_class(self):
        from ..invigilators.invigilator_slop import InvigilatorSlop

        return InvigilatorSlop

    def to_dict(self, add_edsl_version: bool = True):
        data = {
            "question_name": self.question_name,
            "question_text": self.question_text,
            "provider": self.provider,
            "include_segments": self.include_segments,
            "include_raw_response": self.include_raw_response,
            "public_dashboard_link": self.public_dashboard_link,
            "min_text_length": self.min_text_length,
            "on_short_text": self.on_short_text,
            "timeout_seconds": self.timeout_seconds,
            "poll_interval": self.poll_interval,
            "question_type": self.question_type,
        }
        if self._answering_instructions is not None:
            data["answering_instructions"] = self._answering_instructions
        if self._question_presentation is not None:
            data["question_presentation"] = self._question_presentation
        if add_edsl_version:
            from .. import __version__

            data["edsl_version"] = __version__
            data["edsl_class_name"] = "QuestionBase"
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "QuestionSlop":
        local_data = data.copy()
        local_data.pop("edsl_version", None)
        local_data.pop("edsl_class_name", None)
        local_data.pop("question_type", None)
        return cls(**local_data)

    @classmethod
    @inject_exception
    def example(cls, randomize: bool = False) -> "QuestionSlop":
        addition = "" if not randomize else str(uuid4())
        return cls(
            question_name="slop_score",
            question_text=f"This is a short detector test.{addition}",
            min_text_length=0,
        )

