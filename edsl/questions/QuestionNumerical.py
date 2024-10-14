from __future__ import annotations

# from decimal import Decimal
from random import uniform
from typing import Any, Optional, Union, Literal

from pydantic import BaseModel, Field, field_validator

from edsl.exceptions import QuestionAnswerValidationError
from edsl.questions.QuestionBase import QuestionBase
from edsl.questions.descriptors import NumericalOrNoneDescriptor
from edsl.questions.decorators import inject_exception
from edsl.questions.ResponseValidatorABC import ResponseValidatorABC
from edsl.exceptions.questions import QuestionAnswerValidationError


def create_numeric_response(
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    permissive=False,
):
    field_kwargs = {}
    if not permissive:
        field_kwargs = {}
        if min_value is not None:
            field_kwargs["ge"] = min_value
        if max_value is not None:
            field_kwargs["le"] = max_value

    class ConstrainedNumericResponse(BaseModel):
        answer: Union[int, float] = Field(**field_kwargs)
        comment: Optional[str] = Field(None)
        generated_tokens: Optional[Any] = Field(None)

    return ConstrainedNumericResponse


class NumericalResponseValidator(ResponseValidatorABC):
    required_params = ["min_value", "max_value", "permissive"]

    valid_examples = [
        ({"answer": 1}, {"min_value": 0, "max_value": 10}),
        ({"answer": 1}, {"min_value": None, "max_value": None}),
    ]

    invalid_examples = [
        ({"answer": 10}, {"min_value": 0, "max_value": 5}, "Answer is out of range"),
        ({"answer": "ten"}, {"min_value": 0, "max_value": 5}, "Answer is not a number"),
        ({}, {"min_value": 0, "max_value": 5}, "Answer key is missing"),
    ]

    def fix(self, response, verbose=False):
        response_text = str(response).lower()
        import re

        if verbose:
            print(f"Ivalid generated tokens was was: {response_text}")
        pattern = r"\b\d+(?:\.\d+)?\b"
        match = re.search(pattern, response_text.replace(",", ""))
        solution = match.group(0) if match else response.get("answer")
        if verbose:
            print("Proposed solution is: ", solution)
        if "comment" in response:
            return {"answer": solution, "comment": response["comment"]}
        else:
            return {"answer": solution}

    def _check_constraints(self, pydantic_edsl_answer: BaseModel):
        pass


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
        permissive: bool = False,
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
        self.permissive = permissive

    def create_response_model(self):
        return create_numeric_response(self.min_value, self.max_value, self.permissive)

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
    def example(cls, include_comment=False) -> QuestionNumerical:
        """Return an example question."""
        return cls(
            question_name="age",
            question_text="You are a 45 year old man. How old are you in years?",
            min_value=0,
            max_value=86.7,
            include_comment=include_comment,
        )


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
