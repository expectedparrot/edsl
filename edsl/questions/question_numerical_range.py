"""Question type for an inclusive numerical interval."""

from __future__ import annotations

from random import uniform
from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    create_model,
    model_validator,
)

from .decorators import inject_exception
from .descriptors import NumericalOrNoneDescriptor, QuestionTextDescriptor
from .exceptions import QuestionCreationValidationError
from . import markdown_layout as md
from .question_base import QuestionBase
from .response_validator_abc import ResponseValidatorABC


class NumericalRangeResponseValidator(ResponseValidatorABC):
    required_params = []
    valid_examples = [({"answer": {"min": 2, "max": 8}}, {})]
    invalid_examples = [
        ({"answer": {"min": 8, "max": 2}}, {}, "minimum cannot exceed maximum")
    ]


def create_numerical_range_response(
    min_value: Optional[float], max_value: Optional[float]
):
    class NumericalInterval(BaseModel):
        min: FiniteFloat = Field(ge=min_value, le=max_value)
        max: FiniteFloat = Field(ge=min_value, le=max_value)
        model_config = ConfigDict(extra="forbid")

        @model_validator(mode="after")
        def validate_interval(self):
            if self.min > self.max:
                raise ValueError("The interval minimum cannot exceed its maximum.")
            return self

    return create_model(
        "NumericalRangeResponse",
        answer=(NumericalInterval, ...),
        comment=(Optional[str], None),
        generated_tokens=(Optional[str], None),
        reasoning_summary=(Optional[str], None),
        __config__=ConfigDict(extra="forbid"),
    )


class QuestionNumericalRange(QuestionBase):
    """Ask for an inclusive interval with ``min`` and ``max`` numeric endpoints.

    Optional ``min_value`` and ``max_value`` bound both submitted endpoints.

    >>> q = QuestionNumericalRange("price", "What price range?", min_value=0, max_value=100)
    >>> q.response_model(answer={"min": 10, "max": 25}).model_dump()["answer"]
    {'min': 10.0, 'max': 25.0}
    """

    question_type = "numerical_range"
    question_text = QuestionTextDescriptor()
    min_value = NumericalOrNoneDescriptor()
    max_value = NumericalOrNoneDescriptor()
    response_validator_class = NumericalRangeResponseValidator
    _response_model = None

    def __init__(
        self,
        question_name: str,
        question_text: str,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        include_comment: bool = True,
        answering_instructions: Optional[str] = None,
        question_presentation: Optional[str] = None,
    ):
        if min_value is not None and max_value is not None and min_value > max_value:
            raise QuestionCreationValidationError("min_value cannot exceed max_value.")
        self.question_name = question_name
        self.question_text = question_text
        self.min_value = min_value
        self.max_value = max_value
        self.include_comment = include_comment
        self.answering_instructions = answering_instructions
        self.question_presentation = question_presentation

    def create_response_model(self):
        return create_numerical_range_response(self.min_value, self.max_value)

    def _simulate_answer(self) -> dict:
        lower = self.min_value if self.min_value is not None else 0.0
        upper = self.max_value if self.max_value is not None else 100.0
        if self.min_value is None and self.max_value is not None:
            lower = min(0.0, upper)
        if self.max_value is None and self.min_value is not None:
            upper = max(100.0, lower)
        first, second = sorted((uniform(lower, upper), uniform(lower, upper)))
        return {"answer": {"min": first, "max": second}}

    def _markdown_answer(self, option_notes):
        return (
            "Enter a minimum and maximum"
            + md.bounds(self.min_value, self.max_value)
            + "."
        )

    @property
    def question_html_content(self) -> str:
        from jinja2 import Template

        return Template(
            """
            <div class="numerical-range-question">
              <label for="{{ name }}_min">Minimum</label>
              <input type="number" id="{{ name }}_min" name="{{ name }}_min"
                     {% if min_value is not none %}min="{{ min_value }}"{% endif %}
                     {% if max_value is not none %}max="{{ max_value }}"{% endif %}>
              <label for="{{ name }}_max">Maximum</label>
              <input type="number" id="{{ name }}_max" name="{{ name }}_max"
                     {% if min_value is not none %}min="{{ min_value }}"{% endif %}
                     {% if max_value is not none %}max="{{ max_value }}"{% endif %}>
            </div>
            """
        ).render(
            name=self.question_name,
            min_value=self.min_value,
            max_value=self.max_value,
        )

    @classmethod
    @inject_exception
    def example(cls) -> "QuestionNumericalRange":
        return cls(
            question_name="acceptable_price",
            question_text="What price range would you consider acceptable?",
            min_value=0,
            max_value=1000,
        )
