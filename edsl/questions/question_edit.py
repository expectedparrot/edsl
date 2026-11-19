"""A question that asks a respondent to revise supplied text."""

from __future__ import annotations

from typing import Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, field_validator

from .decorators import inject_exception
from .question_base import QuestionBase
from .response_validator_abc import ResponseValidatorABC


class EditChange(BaseModel):
    """One span in a Humanize edit diff."""

    type: Literal["equal", "insert", "delete"]
    text: str


class EditResponse(BaseModel):
    """The final revised text, with optional Humanize change-tracking data."""

    answer: str
    original_text: Optional[str] = None
    changes: Optional[list[EditChange]] = None
    generated_tokens: Optional[str] = None

    @field_validator("answer", mode="before")
    @classmethod
    def convert_answer_to_string(cls, value):
        if value is not None:
            return str(value)
        return value


class EditResponseValidator(ResponseValidatorABC):
    """Validate a revised text response."""

    required_params = []
    valid_examples = [({"answer": "The edited draft."}, {})]
    invalid_examples = [({"answer": None}, {}, "Answer code must not be missing.")]


class QuestionEdit(QuestionBase):
    """A question that asks for a direct revision of supplied text.

    The answer is the complete revised text. In Humanize, respondents edit the
    text directly and the interface shows insertions and deletions as tracked
    changes. `text_to_edit` may contain EDSL piping or scenario templates.

    >>> q = QuestionEdit(
    ...     question_name="revise",
    ...     question_text="Improve clarity without changing the meaning.",
    ...     text_to_edit="The report was made by the team and it has many details.",
    ... )
    >>> q.question_type
    'edit'
    """

    question_type = "edit"
    _response_model = EditResponse
    response_validator_class = EditResponseValidator

    def __init__(
        self,
        question_name: str,
        question_text: str,
        text_to_edit: str,
        answering_instructions: Optional[str] = None,
        question_presentation: Optional[str] = None,
    ):
        self.question_name = question_name
        self.question_text = question_text
        self._text_to_edit = text_to_edit
        self.answering_instructions = answering_instructions
        self.question_presentation = question_presentation

    @property
    def text_to_edit(self) -> str:
        return self._text_to_edit

    @text_to_edit.setter
    def text_to_edit(self, value: str) -> None:
        self._text_to_edit = value

    @property
    def question_html_content(self) -> str:
        from html import escape

        return (
            f"<div><p>{escape(self.question_text)}</p>"
            f"<blockquote>{escape(self.text_to_edit)}</blockquote>"
            f'<textarea id="{escape(self.question_name)}" '
            f'name="{escape(self.question_name)}"></textarea></div>'
        )

    @classmethod
    @inject_exception
    def example(cls, randomize: bool = False) -> "QuestionEdit":
        suffix = str(uuid4()) if randomize else ""
        return cls(
            question_name=f"revise_text{suffix}",
            question_text="Improve this draft for clarity without changing its meaning.",
            text_to_edit="Our product helps teams make better decisions faster.",
        )
