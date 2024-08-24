from __future__ import annotations
import textwrap
from random import uniform
from typing import Any, Optional, Union

from edsl.exceptions import QuestionAnswerValidationError
from edsl.questions.QuestionBase import QuestionBase
from edsl.questions.descriptors import NumericalOrNoneDescriptor

from edsl.questions.decorators import inject_exception

from edsl.questions.AnswerNumerical import AnswerNumerical
from edsl.prompts import Prompt

from edsl.questions.ResponseValidatorABC import ResponseValidatorABC
from edsl.questions.ResponseValidatorABC import BaseResponse

from decimal import Decimal
from pydantic import field_validator
from edsl.questions.ResponseValidatorABC import ResponseValidatorABC
from edsl.questions.ResponseValidatorABC import BaseResponse
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator
from typing import Optional


class QuestionAnswerValidationError(ValueError):
    pass


class NumericResponse(BaseModel):
    """
    >>> nr = NumericResponse(answer=1, comment="I like custard")
    >>> nr.model_dump()
    {'answer': Decimal('1'), 'comment': 'I like custard'}
    """

    answer: Decimal
    comment: Optional[str] = None

    @field_validator("answer", mode="before")
    @classmethod
    def parse_numeric(cls, v):
        if isinstance(v, str):
            v = v.replace(",", "")
        try:
            return Decimal(v)
        except:
            raise QuestionAnswerValidationError(f"Invalid numeric value: {v}")


def create_numeric_response(
    min_value: Optional[Decimal] = None, max_value: Optional[Decimal] = None
):
    field_kwargs = {}
    if min_value is not None:
        field_kwargs["ge"] = min_value
    if max_value is not None:
        field_kwargs["le"] = max_value

    class ConstrainedNumericResponse(NumericResponse):
        answer: Decimal = Field(**field_kwargs)

    return ConstrainedNumericResponse


class NumericalResponseValidator(ResponseValidatorABC):
    required_params = ["min_value", "max_value"]

    valid_examples = [
        ({"answer": 1}, {"min_value": 0, "max_value": 10}),
        ({"answer": 1}, {"min_value": None, "max_value": None}),
    ]

    invalid_examples = [
        ({"answer": 10}, {"min_value": 0, "max_value": 5}, "Answer if out of range"),
        ({"answer": "ten"}, {"min_value": 0, "max_value": 5}, "Answer is not a number"),
        ({}, {"min_value": 0, "max_value": 5}, "Answer key is missing"),
    ]

    def custom_validate(self, response) -> NumericResponse:
        if self.min_value is not None:
            if response.answer < self.min_value:
                raise QuestionAnswerValidationError(
                    f"Answer must be at least {self.min_value}"
                )
        if self.max_value:
            if response.answer > self.max_value:
                raise QuestionAnswerValidationError(
                    f"Answer must be at most {self.max_value}"
                )
        return response.dict()


class QuestionNumerical(QuestionBase):
    """This question prompts the agent to answer with a numerical value.

    >>> QuestionNumerical.self_check()

    """

    question_type = "numerical"
    min_value: Optional[float] = NumericalOrNoneDescriptor()
    max_value: Optional[float] = NumericalOrNoneDescriptor()

    _response_model = None
    response_validator_class = NumericalResponseValidator

    def __init__(
        self,
        question_name: str,
        question_text: str,
        min_value: Optional[Union[int, float]] = None,
        max_value: Optional[Union[int, float]] = None,
        include_comment: bool = True,
        question_presentation: Optional[str] = None,
        answering_instructions: Optional[str] = None,
    ):
        """Initialize the question.

        :param question_name: The name of the question.
        :param question_text: The text of the question.
        :param min_value: The minimum value of the answer.
        :param max_value: The maximum value of the answer.
        """
        self.question_name = question_name
        self.question_text = question_text
        self.min_value = min_value
        self.max_value = max_value

        self.include_comment = include_comment
        self.question_presentation = question_presentation
        self.answering_instructions = answering_instructions

    def create_response_model(self):
        return create_numeric_response(self.min_value, self.max_value)

    ################
    # Answer methods
    ################

    @property
    def question_html_content(self) -> str:
        from jinja2 import Template

        question_html_content = Template(
            """
        <div>
        <input type="number" id="{{ question_name }}" name="{{ question_name }}">
        </div>
        """
        ).render(question_name=self.question_name)
        return question_html_content

    ################
    # Helpful methods
    ################
    @classmethod
    @inject_exception
    def example(cls) -> QuestionNumerical:
        """Return an example question."""
        return cls(
            question_name="age",
            question_text="How old are you in years?",
            min_value=0,
            max_value=86.7,
        )


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
