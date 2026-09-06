from __future__ import annotations

from typing import Optional
from uuid import uuid4

from pydantic import AnyUrl, BaseModel, TypeAdapter, field_validator

from .decorators import inject_exception
from .question_base import QuestionBase
from .response_validator_abc import ResponseValidatorABC


class URLResponse(BaseModel):
    """Response model requiring the answer to be an absolute URL."""

    answer: str
    comment: Optional[str] = None
    generated_tokens: Optional[str] = None

    @field_validator("answer")
    @classmethod
    def validate_url(cls, value: str) -> str:
        # Validate with Pydantic, but retain the caller's string rather than
        # returning a Url object or normalizing the URL.
        TypeAdapter(AnyUrl).validate_python(value)
        return value


class URLResponseValidator(ResponseValidatorABC):
    required_params = []
    valid_examples = [({"answer": "https://example.com/resource?id=1"}, {})]
    invalid_examples = [
        ({"answer": "example.com"}, {}, "Answer must be a valid absolute URL."),
        ({"answer": "/relative/path"}, {}, "Answer must be a valid absolute URL."),
    ]


class QuestionURL(QuestionBase):
    """A question whose answer must be a valid absolute URL."""

    question_type = "url"
    _response_model = URLResponse
    response_validator_class = URLResponseValidator

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
            f'<input type="url" id="{self.question_name}" '
            f'name="{self.question_name}">'
        )

    @classmethod
    @inject_exception
    def example(cls, randomize: bool = False) -> "QuestionURL":
        addition = "" if not randomize else f" {uuid4()}"
        return cls(
            question_name="website_url",
            question_text=f"What is the URL for the EDSL website?{addition}",
        )
