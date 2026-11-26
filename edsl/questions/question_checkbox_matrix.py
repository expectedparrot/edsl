"""Checkbox matrix question type."""

from __future__ import annotations

import random
from html import escape
from typing import Any, Dict, List, Optional, Type, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .decorators import inject_exception
from .descriptors import (
    BaseDescriptor,
    OptionLabelDescriptor,
    QuestionOptionsDescriptor,
    QuestionTextDescriptor,
)
from .exceptions import QuestionCreationValidationError
from . import markdown_layout as md
from .question_base import QuestionBase
from .response_validator_abc import ResponseValidatorABC


class CheckboxMatrixResponseValidator(ResponseValidatorABC):
    """Validate model responses without silently changing their selections."""

    required_params = ["question_items", "question_options", "permissive"]
    valid_examples = [
        (
            {"answer": {"Monday": ["Exercise"]}},
            {
                "question_items": ["Monday"],
                "question_options": ["Exercise"],
                "permissive": False,
            },
        )
    ]
    invalid_examples = [
        (
            {"answer": {"Monday": ["Unknown"]}},
            {
                "question_items": ["Monday"],
                "question_options": ["Exercise"],
                "permissive": False,
            },
            "Invalid option",
        )
    ]

    def fix(self, response, verbose=False):
        return response


class MatrixItemsDescriptor(BaseDescriptor):
    """Validate row labels without applying option-selection constraints."""

    def validate(self, value, instance):
        if not isinstance(value, list) or len(value) < 1:
            raise QuestionCreationValidationError("question_items must be a non-empty list.")
        if not all(isinstance(item, str) and item for item in value):
            raise QuestionCreationValidationError("question_items must contain non-empty strings.")
        if len(value) != len(set(value)):
            raise QuestionCreationValidationError("question_items must be unique.")


def create_checkbox_matrix_response(
    question_items: List[str],
    question_options: List[Union[int, str, float]],
    min_selections: int,
    max_selections: int,
    permissive: bool = False,
) -> Type[BaseModel]:
    """Build a response model with per-row checkbox validation."""

    class CheckboxMatrixResponse(BaseModel):
        answer: Dict[str, List[Any]] = Field(description="Selected options for each row")
        comment: Optional[str] = None
        generated_tokens: Optional[Any] = None

        model_config = ConfigDict(extra="allow" if permissive else "forbid")

        @model_validator(mode="after")
        def validate_rows(self):
            answer = self.answer
            missing = [row for row in question_items if row not in answer]
            extra = [row for row in answer if row not in question_items]
            if not permissive and missing:
                raise ValueError(f"Missing responses for rows: {missing}")
            if not permissive and extra:
                raise ValueError(f"Unexpected rows: {extra}")

            for row, selected in answer.items():
                if permissive:
                    continue
                invalid = [
                    value
                    for value in selected
                    if not any(
                        type(value) is type(option) and value == option
                        for option in question_options
                    )
                ]
                if invalid:
                    raise ValueError(f"Invalid options for row {row!r}: {invalid}")
                if len(selected) != len(set((type(value).__name__, repr(value)) for value in selected)):
                    raise ValueError(f"Duplicate selections for row {row!r}")
                if not min_selections <= len(selected) <= max_selections:
                    raise ValueError(
                        f"Row {row!r} must have between {min_selections} and {max_selections} selections; got {len(selected)}"
                    )
            return self

    return CheckboxMatrixResponse


class QuestionCheckboxMatrix(QuestionBase):
    """A grid question allowing multiple selected options in each row.

    Answers are dictionaries mapping each row label to a list of selected option
    values, for example ``{"Monday": ["Exercise", "Cooking"]}``.
    """

    question_type = "checkbox_matrix"
    question_text = QuestionTextDescriptor()
    question_items = MatrixItemsDescriptor()
    question_options = QuestionOptionsDescriptor()
    option_labels = OptionLabelDescriptor()
    response_validator_class = CheckboxMatrixResponseValidator
    _response_model = None

    @property
    def min_selections(self):
        return self.__dict__.get("_min_selections", 0)

    @min_selections.setter
    def min_selections(self, value):
        self.__dict__["_min_selections"] = value

    @property
    def max_selections(self):
        return self.__dict__.get("_max_selections", len(self.question_options))

    @max_selections.setter
    def max_selections(self, value):
        self.__dict__["_max_selections"] = value

    @property
    def permissive(self):
        return self.__dict__.get("_permissive", False)

    @permissive.setter
    def permissive(self, value):
        self.__dict__["_permissive"] = value

    def __init__(
        self,
        question_name: str,
        question_text: str,
        question_items: List[str],
        question_options: List[Union[int, str, float]],
        option_labels: Optional[Dict[Union[int, str, float], str]] = None,
        min_selections: Optional[int] = None,
        max_selections: Optional[int] = None,
        include_comment: bool = True,
        answering_instructions: Optional[str] = None,
        question_presentation: Optional[str] = None,
        permissive: bool = False,
    ):
        self.question_name = question_name
        self.question_text = question_text
        self.min_selections = 0 if min_selections is None else min_selections
        self.max_selections = (
            len(question_options) if max_selections is None else max_selections
        )
        if self.min_selections < 0 or self.max_selections < self.min_selections:
            raise QuestionCreationValidationError(
                "Selection bounds must be non-negative and max_selections must be "
                "at least min_selections."
            )
        if self.max_selections > len(question_options):
            raise QuestionCreationValidationError(
                "max_selections cannot exceed the number of question_options."
            )
        self.question_items = question_items
        self.question_options = question_options
        self.option_labels = option_labels or {}
        self.include_comment = include_comment
        self.answering_instructions = answering_instructions
        self.question_presentation = question_presentation
        self.permissive = permissive

    def create_response_model(self) -> Type[BaseModel]:
        return create_checkbox_matrix_response(
            self.question_items,
            self.question_options,
            self.min_selections,
            self.max_selections,
            self.permissive,
        )

    def _simulate_answer(self) -> dict:
        answer = {}
        for row in self.question_items:
            count = random.randint(self.min_selections, self.max_selections)
            answer[row] = random.sample(self.question_options, count)
        return {"answer": answer, "comment": "Sample checkbox matrix response"}

    def _markdown_answer(self, option_notes):
        return md.matrix(
            self,
            "For each row: "
            + md.select_count(self.min_selections, self.max_selections),
            marker="☐",
        )

    @property
    def question_html_content(self) -> str:
        from jinja2 import Template

        return Template(
            """
            <table class="checkbox-matrix-question">
              <thead><tr><th></th>
                {% for option in question_options %}
                <th>{{ option_labels.get(option, option) }}</th>
                {% endfor %}
              </tr></thead>
              <tbody>
                {% for item in question_items %}
                <tr><th>{{ item }}</th>
                  {% for option in question_options %}
                  <td><input type="checkbox" name="{{ question_name }}_{{ item }}"
                             value="{{ option }}"></td>
                  {% endfor %}
                </tr>
                {% endfor %}
              </tbody>
            </table>
            """
        ).render(
            question_name=escape(self.question_name, quote=True),
            question_items=[escape(item, quote=True) for item in self.question_items],
            question_options=[escape(str(option), quote=True) for option in self.question_options],
            option_labels={
                key: escape(str(label), quote=True)
                for key, label in self.option_labels.items()
            },
        )

    @classmethod
    @inject_exception
    def example(cls) -> "QuestionCheckboxMatrix":
        return cls(
            question_name="weekly_activities",
            question_text="Which activities do you do on each day?",
            question_items=["Monday", "Tuesday", "Wednesday"],
            question_options=["Exercise", "Cooking", "Reading"],
            min_selections=0,
            max_selections=2,
        )
