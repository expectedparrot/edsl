from __future__ import annotations
from typing import Union, Optional, Dict, List, Any

from pydantic import BaseModel, Field, field_validator
from jinja2 import Template
import random
from .question_base import QuestionBase
from .descriptors import (
    QuestionOptionsDescriptor,
    OptionLabelDescriptor,
    QuestionTextDescriptor,
)
from .response_validator_abc import ResponseValidatorABC
from .decorators import inject_exception

from .exceptions import (
    QuestionCreationValidationError,
)


def create_matrix_response(
    question_items: List[str],
    question_options: List[Union[int, str, float]],
    permissive: bool = False,
):
    """Create a response model for matrix questions.

    The response model validates that:
    1. All question items are answered
    2. Each answer is from the allowed options
    """

    if permissive:

        class MatrixResponse(BaseModel):
            answer: Dict[str, Any]
            comment: Optional[str] = None
            generated_tokens: Optional[Any] = None

    else:

        class MatrixResponse(BaseModel):
            answer: Dict[str, Union[int, str, float]] = Field(
                ..., description="Mapping of items to selected options"
            )
            comment: Optional[str] = None
            generated_tokens: Optional[Any] = None

            @field_validator("answer")
            def validate_answer(cls, v, values, **kwargs):
                # Check that all items have responses
                if not all(item in v for item in question_items):
                    missing = set(question_items) - set(v.keys())
                    from .exceptions import QuestionAnswerValidationError
                    raise QuestionAnswerValidationError(f"Missing responses for items: {missing}")

                # Check that all responses are valid options
                if not all(answer in question_options for answer in v.values()):
                    invalid = [ans for ans in v.values() if ans not in question_options]
                    from .exceptions import QuestionAnswerValidationError
                    raise QuestionAnswerValidationError(f"Invalid options selected: {invalid}")
                return v

    return MatrixResponse


class MatrixResponseValidator(ResponseValidatorABC):
    required_params = ["question_items", "question_options", "permissive"]

    valid_examples = [
        (
            {"answer": {"Item1": 1, "Item2": 2}},
            {
                "question_items": ["Item1", "Item2"],
                "question_options": [1, 2, 3],
            },
        )
    ]

    invalid_examples = [
        (
            {"answer": {"Item1": 1}},
            {
                "question_items": ["Item1", "Item2"],
                "question_options": [1, 2, 3],
            },
            "Missing responses for some items",
        ),
        (
            {"answer": {"Item1": 4, "Item2": 5}},
            {
                "question_items": ["Item1", "Item2"],
                "question_options": [1, 2, 3],
            },
            "Invalid options selected",
        ),
    ]

    def fix(self, response, verbose=False):
        if verbose:
            print(f"Fixing matrix response: {response}")

        # If we have generated tokens, try to parse them
        if "generated_tokens" in response:
            try:
                import json

                fixed = json.loads(response["generated_tokens"])
                if isinstance(fixed, dict):
                    # Map numeric keys to question items
                    mapped_answer = {}
                    for idx, item in enumerate(self.question_items):
                        if str(idx) in fixed:
                            mapped_answer[item] = fixed[str(idx)]
                    if (
                        mapped_answer
                    ):  # Only return if we successfully mapped some answers
                        return {"answer": mapped_answer}
            except (ValueError, KeyError, TypeError):
                # Just continue to the next parsing attempt
                pass

        # If answer uses numeric keys, map them to question items
        if "answer" in response and isinstance(response["answer"], dict):
            if all(str(key).isdigit() for key in response["answer"].keys()):
                mapped_answer = {}
                for idx, item in enumerate(self.question_items):
                    if str(idx) in response["answer"]:
                        mapped_answer[item] = response["answer"][str(idx)]
                if mapped_answer:  # Only update if we successfully mapped some answers
                    response["answer"] = mapped_answer

        return response


class QuestionMatrix(QuestionBase):
    """A question that presents a matrix/grid where multiple items are rated using the same scale."""

    question_type = "matrix"
    question_text: str = QuestionTextDescriptor()
    question_items: List[str] = QuestionOptionsDescriptor()
    question_options: List[Union[int, str, float]] = QuestionOptionsDescriptor()
    option_labels: Optional[Dict[Union[int, str, float], str]] = OptionLabelDescriptor()

    _response_model = None
    response_validator_class = MatrixResponseValidator

    def __init__(
        self,
        question_name: str,
        question_text: str,
        question_items: List[str],
        question_options: List[Union[int, str, float]],
        option_labels: Optional[Dict[Union[int, str, float], str]] = None,
        include_comment: bool = True,
        answering_instructions: Optional[str] = None,
        question_presentation: Optional[str] = None,
        permissive: bool = False,
    ):
        """Initialize a matrix question.

        Args:
            question_name: The name of the question
            question_text: The text of the question
            question_items: List of items to be rated
            question_options: List of rating options
            option_labels: Optional mapping of options to their labels
            include_comment: Whether to include a comment field
            answering_instructions: Optional custom instructions
            question_presentation: Optional custom presentation
            permissive: Whether to strictly validate responses
        """
        self.question_name = question_name

        try:
            self.question_text = question_text
        except Exception as e:
            raise QuestionCreationValidationError(
                "question_text cannot be empty or too short!"
            ) from e

        self.question_items = question_items
        self.question_options = question_options
        self.option_labels = option_labels or {}

        self.include_comment = include_comment
        self.answering_instructions = answering_instructions
        self.question_presentation = question_presentation
        self.permissive = permissive

    def create_response_model(self):
        return create_matrix_response(
            self.question_items, self.question_options, self.permissive
        )

    @property
    def question_html_content(self) -> str:
        """Generate HTML representation of the matrix question."""
        template = Template(
            """
        <table class="matrix-question">
            <tr>
                <th></th>
                {% for option in question_options %}
                <th>
                    {{ option }}
                    {% if option in option_labels %}
                    <br>
                    <small>{{ option_labels[option] }}</small>
                    {% endif %}
                </th>
                {% endfor %}
            </tr>
            {% for item in question_items %}
            <tr>
                <td>{{ item }}</td>
                {% for option in question_options %}
                <td>
                    <input type="radio" 
                           name="{{ question_name }}_{{ item }}" 
                           value="{{ option }}"
                           id="{{ question_name }}_{{ item }}_{{ option }}">
                </td>
                {% endfor %}
            </tr>
            {% endfor %}
        </table>
        """
        )

        return template.render(
            question_name=self.question_name,
            question_items=self.question_items,
            question_options=self.question_options,
            option_labels=self.option_labels,
        )

    @classmethod
    @inject_exception
    def example(cls) -> QuestionMatrix:
        """Return an example matrix question."""
        return cls(
            question_name="child_happiness",
            question_text="How happy would you be with different numbers of children?",
            question_items=[
                "No children",
                "1 child",
                "2 children",
                "3 or more children",
            ],
            question_options=[1, 2, 3, 4, 5],
            option_labels={1: "Very sad", 3: "Neutral", 5: "Extremely happy"},
        )

    def _simulate_answer(self) -> dict:
        """Simulate a random valid answer."""
        return {
            "answer": {
                item: random.choice(self.question_options)
                for item in self.question_items
            }
        }


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
