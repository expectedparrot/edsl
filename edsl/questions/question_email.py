"""EDSL question for collecting and validating email addresses."""

from __future__ import annotations

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

    _local_part_extra_chars = frozenset(".!#$%&'*+/=?^`{|}~-")
    _domain_extra_chars = frozenset(".-_")
    _wrapping_quotes = frozenset("\"'`")

    @classmethod
    def _is_local_part_char(cls, char: str) -> bool:
        return char == "_" or char.isalnum() or char in cls._local_part_extra_chars

    @classmethod
    def _is_domain_char(cls, char: str) -> bool:
        return char.isalnum() or char in cls._domain_extra_chars

    @staticmethod
    def _normalize_candidate(candidate: str) -> Optional[str]:
        try:
            return str(EmailResponse.model_validate({"answer": candidate}).answer)
        except Exception:
            return None

    def fix(self, response: dict, verbose: bool = False) -> dict:
        """Recover the first valid email address embedded in a reply.

        Scan from each ``@`` so malformed text without an at-sign does not
        trigger repeated regex backtracking. Validate the complete candidate
        before trimming punctuation, since several punctuation characters are
        valid at the start of an email local part.
        """
        answer = response.get("answer")
        if isinstance(answer, dict):
            answer = answer.get("answer")
        if not isinstance(answer, str):
            return response

        at_index = answer.find("@")
        while at_index != -1:
            local_start = at_index
            while local_start > 0 and self._is_local_part_char(
                answer[local_start - 1]
            ):
                local_start -= 1

            domain_end = at_index + 1
            while domain_end < len(answer) and self._is_domain_char(
                answer[domain_end]
            ):
                domain_end += 1

            candidate = answer[local_start:domain_end]

            # Quotes and backticks can be wrappers, but they are also allowed
            # in local parts. Treat them as wrappers only when they are paired.
            if (
                candidate
                and candidate[0] in self._wrapping_quotes
                and domain_end < len(answer)
                and answer[domain_end] == candidate[0]
            ):
                candidate = candidate[1:]

            normalized = self._normalize_candidate(candidate)
            if normalized is None:
                trimmed_candidate = candidate.strip(".,;:!?)]}>\"'`")
                if trimmed_candidate != candidate:
                    normalized = self._normalize_candidate(trimmed_candidate)

            if normalized is not None:
                fixed_response = dict(response)
                fixed_response["answer"] = normalized
                return fixed_response

            at_index = answer.find("@", at_index + 1)

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
