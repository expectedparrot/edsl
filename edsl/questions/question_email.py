"""EDSL question for collecting and validating email addresses."""

from __future__ import annotations

import re
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, EmailStr

from .decorators import inject_exception
from .question_base import QuestionBase
from .response_validator_abc import ResponseValidatorABC


class EmailResponse(BaseModel):
    """Response model that validates an email address."""

    answer: EmailStr
    comment: Optional[str] = None
    generated_tokens: Optional[str] = None


class EmailResponseValidator(ResponseValidatorABC):
    required_params = []
    valid_examples = [({"answer": "researcher@example.com"}, {})]
    invalid_examples = [
        ({"answer": "not-an-email"}, {}, "Answer must be a valid email address."),
        ({"answer": "missing-domain@"}, {}, "Answer must be a valid email address."),
    ]

    _email_candidate_pattern = re.compile(
        r"(?<![\w.+-])[\w.!#$%&'*+/=?^`{|}~-]+@[\w.-]+", re.UNICODE
    )

    def fix(self, response: dict, verbose: bool = False) -> dict:
        """Recover and validate the first email address embedded in a reply."""
        answer = response.get("answer")
        if isinstance(answer, dict):
            answer = answer.get("answer")
        if not isinstance(answer, str):
            return response

        for match in self._email_candidate_pattern.finditer(answer):
            candidate = match.group(0).strip(".,;:!?)]}>\"'`")
            try:
                normalized = EmailResponse.model_validate({"answer": candidate}).answer
            except Exception:
                continue
            fixed_response = dict(response)
            fixed_response["answer"] = str(normalized)
            return fixed_response

        return response


class QuestionEmail(QuestionBase):
    """A question whose answer must be a valid email address."""

    question_type = "email"
    _response_model = EmailResponse
    response_validator_class = EmailResponseValidator

    def _simulate_answer(self, human_readable: bool = False) -> dict:
        return {
            "answer": "researcher@example.com",
            "comment": "Simulated answer",
        }

    def __init__(
        self,
        question_name: str,
        question_text: str,
        answering_instructions: Optional[str] = None,
        question_presentation: Optional[str] = None,
    ):
        self.question_name = question_name
        self.question_text = question_text
        self.answering_instructions = answering_instructions
        self.question_presentation = question_presentation

    @property
    def question_html_content(self) -> str:
        return (
            f'<input type="email" id="{self.question_name}" '
            f'name="{self.question_name}">'
        )

    @classmethod
    @inject_exception
    def example(cls, randomize: bool = False) -> "QuestionEmail":
        addition = "" if not randomize else f" {uuid4()}"
        return cls(
            question_name="email_address",
            question_text=f"What is your email address?{addition}",
        )
