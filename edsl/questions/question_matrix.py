"""
question_matrix.py

Drop-in replacement for `QuestionMatrix` with a dynamic Pydantic approach
that automatically raises ValidationError for invalid matrix answers.
"""

from __future__ import annotations
from typing import (
    Union,
    Optional,
    Dict,
    List,
    Any,
    Type,
    get_args,
    Literal
)
import random

from pydantic import BaseModel, Field, create_model, ValidationError
from jinja2 import Template

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
    QuestionAnswerValidationError,  # If you still want to raise custom exceptions
)


def create_matrix_response(
    question_items: List[str],
    question_options: List[Union[int, str, float]],
    permissive: bool = False,
) -> Type[BaseModel]:
    """
    Create a dynamic Pydantic model for matrix questions.

    If `permissive=False`, each item is a required field with a `Literal[...]` type
    so that only the given question_options are allowed.
    If `permissive=True`, each item can have any value, and extra items are allowed.
    """

    # If non-permissive, build a Literal for each valid option
    # e.g. Literal[1,2,3] or Literal["Yes","No"] or a mix
    if not permissive:
        # If question_options is empty (edge case), fall back to 'Any'
        if question_options:
            AllowedOptions = Literal[tuple(question_options)]  # type: ignore
        else:
            AllowedOptions = Any
    else:
        # Permissive => let each item be anything
        AllowedOptions = Any

    # Build field definitions for an "AnswerSubModel", where each
    # question_item is a required field with type AllowedOptions
    field_definitions = {}
    for item in question_items:
        field_definitions[item] = (AllowedOptions, Field(...))  # required

    # Dynamically create the submodel
    MatrixAnswerSubModel = create_model(
        "MatrixAnswerSubModel",
        __base__=BaseModel,
        **field_definitions
    )

    # Build the top-level model with `answer` + optional `comment`
    class MatrixResponse(BaseModel):
        answer: MatrixAnswerSubModel
        comment: Optional[str] = None
        generated_tokens: Optional[Any] = None

        class Config:
            # If permissive=False, forbid extra items in `answer`.
            # If permissive=True, allow them.
            extra = "allow" if permissive else "forbid"

    return MatrixResponse


class MatrixResponseValidator(ResponseValidatorABC):
    """Optional placeholder validator, if still needed for example/fixing logic."""
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
        """
        Example fix() method to try and repair a partially invalid response.
        (This logic is carried over from your original code.)
        """
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
                    if mapped_answer:
                        return {"answer": mapped_answer}
            except (ValueError, KeyError, TypeError):
                pass  # Just continue

        # If answer uses numeric keys, map them to question items
        if "answer" in response and isinstance(response["answer"], dict):
            if all(str(key).isdigit() for key in response["answer"].keys()):
                mapped_answer = {}
                for idx, item in enumerate(self.question_items):
                    if str(idx) in response["answer"]:
                        mapped_answer[item] = response["answer"][str(idx)]
                if mapped_answer:
                    response["answer"] = mapped_answer

        return response


class QuestionMatrix(QuestionBase):
    """
    A question that presents a matrix/grid where multiple items are rated
    or selected from the same set of options.

    This version dynamically builds a Pydantic model at runtime
    (via `create_matrix_response`) and automatically raises ValidationError
    if the user provides an invalid or incomplete answer.
    """

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
        """
        Initialize a matrix question.

        Args:
            question_name: The name of the question
            question_text: The text of the question
            question_items: List of items to be rated or answered
            question_options: Possible answer options (e.g., [1,2,3] or ["Yes","No"])
            option_labels: Optional mapping of options to labels (e.g. {1: "Sad", 5: "Happy"})
            include_comment: Whether to include a comment field
            answering_instructions: Custom instructions
            question_presentation: Custom presentation
            permissive: Whether to allow any values & extra items instead of strictly checking
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

    def create_response_model(self) -> Type[BaseModel]:
        """
        Returns the pydantic model that will parse/validate a user answer.
        """
        return create_matrix_response(
            self.question_items,
            self.question_options,
            self.permissive
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