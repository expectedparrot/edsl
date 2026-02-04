"""
question_matrix_entry.py

Module implementing the matrix entry question type with numeric input validation
"""

from __future__ import annotations
from typing import Union, Optional, Dict, List, Any, Type
import random
import json
import re

from pydantic import (
    BaseModel,
    Field,
    create_model,
    ValidationError,
    model_validator,
    ConfigDict,
)
from jinja2 import Template

from .question_base import QuestionBase
from .descriptors import (
    QuestionTextDescriptor,
    QuestionOptionsDescriptor,
    NumericalOrNoneDescriptor,
)
from .response_validator_abc import ResponseValidatorABC
from .decorators import inject_exception

from .exceptions import (
    QuestionCreationValidationError,
    QuestionAnswerValidationError,
)


class MatrixEntryResponseBase(BaseModel):
    """
    Base model for matrix entry question responses.

    Attributes:
        answer: A dictionary mapping each item to a dictionary of column->numeric value
        comment: Optional comment about the entries
        generated_tokens: Optional token usage data

    Examples:
        >>> # Valid response with two items and three columns
        >>> model = MatrixEntryResponseBase(answer={
        ...     "Trust level": {"No AI Tools": 7.5, "With AI Help": 8.2, "AI Only": 6.1},
        ...     "Satisfaction level": {"No AI Tools": 6.8, "With AI Help": 9.1, "AI Only": 7.3}
        ... })
        >>> model.answer["Trust level"]["No AI Tools"]
        7.5

        >>> # Valid response with a comment
        >>> model = MatrixEntryResponseBase(
        ...     answer={"Trust level": {"No AI Tools": 6, "With AI Help": 8}},
        ...     comment="These ratings are based on my experience"
        ... )
        >>> model.comment
        'These ratings are based on my experience'
    """

    answer: Dict[str, Dict[str, Union[int, float]]]
    comment: Optional[str] = None
    generated_tokens: Optional[Any] = None


def create_matrix_entry_response(
    question_items: List[str],
    question_columns: List[str],
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    permissive: bool = False,
) -> Type[BaseModel]:
    """
    Create a dynamic Pydantic model for matrix entry questions with numeric validation.

    Args:
        question_items: List of items that need responses (rows)
        question_columns: List of column headers
        min_value: Optional minimum value for numeric entries
        max_value: Optional maximum value for numeric entries
        permissive: If True, allows any values and additional items

    Returns:
        A Pydantic model class for validating matrix entry responses

    Examples:
        >>> # Create a model for a 2x3 numeric matrix
        >>> Model = create_matrix_entry_response(
        ...     ["Trust level", "Satisfaction level"],
        ...     ["No AI Tools", "With AI Help", "AI Only"],
        ...     min_value=0,
        ...     max_value=10
        ... )
        >>> # Valid response
        >>> response = Model(answer={
        ...     "Trust level": {"No AI Tools": 7.5, "With AI Help": 8.2, "AI Only": 6.1},
        ...     "Satisfaction level": {"No AI Tools": 6.8, "With AI Help": 9.1, "AI Only": 7.3}
        ... })
        >>> response.answer.model_dump()["Trust level"]["No AI Tools"]
        7.5

        >>> # Invalid: out of range value
        >>> try:
        ...     Model(answer={
        ...         "Trust level": {"No AI Tools": 15.0, "With AI Help": 8.2, "AI Only": 6.1}
        ...     })
        ... except Exception:
        ...     print("Validation error occurred")
        Validation error occurred
    """

    # Define the validation type for numeric values
    NumericValue = Union[int, float]

    # Build field definitions for each item's column responses
    field_definitions = {}
    for item in question_items:
        # Each item maps to a dict of column -> numeric value
        column_fields = {}
        for column in question_columns:
            if permissive:
                column_fields[column] = (
                    Optional[NumericValue],
                    Field(None),
                )  # optional field in permissive mode
            else:
                column_fields[column] = (NumericValue, Field(...))  # required field

        # Create a submodel for this item's column responses
        ItemResponseSubModel = create_model(
            f"{item.replace(' ', '').replace('-', '').replace('.', '')}ResponseSubModel",
            __base__=BaseModel,
            **column_fields,
        )
        if permissive:
            field_definitions[item] = (
                Optional[ItemResponseSubModel],
                Field(None),
            )  # optional in permissive mode
        else:
            field_definitions[item] = (ItemResponseSubModel, Field(...))

    # Dynamically create the answer submodel
    MatrixAnswerSubModel = create_model(
        "MatrixEntryAnswerSubModel", __base__=BaseModel, **field_definitions
    )

    # Create the full response model with custom validation
    class MatrixEntryResponse(MatrixEntryResponseBase):
        """
        Model for matrix entry question responses with validation for numeric values.
        """

        answer: MatrixAnswerSubModel  # Use the dynamically created submodel

        @model_validator(mode="after")
        def validate_matrix_entry_constraints(self):
            """
            Validates that:
            1. All required items have responses
            2. All responses are valid numeric values
            3. Values are within specified range (if not permissive)
            4. All required columns are present for each item
            """
            matrix_answer = self.answer.model_dump()

            # Check that all required items have responses
            missing_items = [
                item for item in question_items if item not in matrix_answer
            ]
            if missing_items and not permissive:
                missing_str = ", ".join(missing_items)
                validation_error = ValidationError.from_exception_data(
                    title="MatrixEntryResponse",
                    line_errors=[
                        {
                            "type": "value_error",
                            "loc": ("answer",),
                            "msg": f"Missing responses for items: {missing_str}",
                            "input": matrix_answer,
                            "ctx": {"missing_items": missing_items},
                        }
                    ],
                )
                raise QuestionAnswerValidationError(
                    message=f"Missing responses for items: {missing_str}",
                    data=self.model_dump(),
                    model=self.__class__,
                    pydantic_error=validation_error,
                )

            # Validate numeric ranges if not permissive
            if not permissive:
                range_violations = {}
                for item_name, item_responses in matrix_answer.items():
                    if isinstance(item_responses, dict):
                        for column, value in item_responses.items():
                            if isinstance(value, (int, float)):
                                if min_value is not None and value < min_value:
                                    range_violations[f"{item_name}.{column}"] = (
                                        f"value {value} < {min_value}"
                                    )
                                if max_value is not None and value > max_value:
                                    range_violations[f"{item_name}.{column}"] = (
                                        f"value {value} > {max_value}"
                                    )

                if range_violations:
                    violations_str = ", ".join(
                        f"{k}: {v}" for k, v in range_violations.items()
                    )
                    validation_error = ValidationError.from_exception_data(
                        title="MatrixEntryResponse",
                        line_errors=[
                            {
                                "type": "value_error",
                                "loc": ("answer",),
                                "msg": f"Values out of range: {violations_str}",
                                "input": matrix_answer,
                                "ctx": {
                                    "range_violations": range_violations,
                                    "min_value": min_value,
                                    "max_value": max_value,
                                },
                            }
                        ],
                    )
                    range_msg = (
                        f"Values must be between {min_value} and {max_value}"
                        if min_value is not None and max_value is not None
                        else (
                            f"Values must be >= {min_value}"
                            if min_value is not None
                            else f"Values must be <= {max_value}"
                        )
                    )
                    raise QuestionAnswerValidationError(
                        message=f"Values out of range: {violations_str}. {range_msg}",
                        data=self.model_dump(),
                        model=self.__class__,
                        pydantic_error=validation_error,
                    )

            return self

        def _json_schema_extra(schema: dict, model_: BaseModel) -> None:
            # Add schema information for better documentation
            if "properties" in schema and "answer" in schema["properties"]:
                schema["properties"]["answer"][
                    "description"
                ] = "Matrix numeric entries for each item and column"
                if min_value is not None or max_value is not None:
                    constraint_desc = (
                        f" (range: {min_value or 'no min'} to {max_value or 'no max'})"
                    )
                    schema["properties"]["answer"]["description"] += constraint_desc

        model_config = ConfigDict(
            extra="allow",  # Always allow extra fields to handle AI response variations
            json_schema_extra=_json_schema_extra,
        )

    return MatrixEntryResponse


class MatrixEntryResponseValidator(ResponseValidatorABC):
    """
    Validator for matrix entry question responses that attempts to fix invalid responses.

    This validator tries multiple approaches to recover valid matrix entry responses from
    malformed inputs, including JSON parsing, numeric extraction, and structured data recovery.
    """

    required_params = [
        "question_items",
        "question_columns",
        "min_value",
        "max_value",
        "permissive",
    ]

    valid_examples = [
        (
            {
                "answer": {
                    "Trust level": {
                        "No AI Tools": 7.5,
                        "With AI Help": 8.2,
                        "AI Only": 6.1,
                    },
                    "Satisfaction level": {
                        "No AI Tools": 6.8,
                        "With AI Help": 9.1,
                        "AI Only": 7.3,
                    },
                }
            },
            {
                "question_items": ["Trust level", "Satisfaction level"],
                "question_columns": ["No AI Tools", "With AI Help", "AI Only"],
                "min_value": 0,
                "max_value": 10,
                "permissive": False,
            },
        ),
    ]

    invalid_examples = [
        (
            {
                "answer": {
                    "Trust level": {
                        "No AI Tools": 15.0,
                        "With AI Help": 8.2,
                    }  # Missing column + out of range
                }
            },
            {
                "question_items": ["Trust level", "Satisfaction level"],
                "question_columns": ["No AI Tools", "With AI Help", "AI Only"],
                "min_value": 0,
                "max_value": 10,
                "permissive": False,
            },
            "Values out of range or missing items",
        ),
    ]

    def fix(self, response, verbose=False):
        """
        Attempts to fix an invalid matrix entry response by trying multiple parsing strategies.

        Args:
            response: The invalid response to fix
            verbose: Whether to print verbose debugging information

        Returns:
            A fixed response dict if fixable, otherwise the original response
        """
        if verbose:
            print(f"Fixing matrix entry response: {response}")

        # If response doesn't have an answer field, nothing to do
        if "answer" not in response:
            if verbose:
                print("Response has no answer field, cannot fix")
            return response

        answer = response["answer"]

        # Strategy 1: If answer is a flat dict with item.column keys, restructure it
        if isinstance(answer, dict):
            # Check if we have flat keys like "Trust level.No AI Tools"
            flat_keys = [k for k in answer.keys() if "." in str(k) or "_" in str(k)]
            if flat_keys:
                if verbose:
                    print(f"Found flat keys to restructure: {flat_keys}")

                restructured = {}
                for key, value in answer.items():
                    # Try different separators
                    parts = None
                    if "." in str(key):
                        parts = str(key).split(".", 1)
                    elif "_" in str(key):
                        parts = str(key).split("_", 1)
                    elif " - " in str(key):
                        parts = str(key).split(" - ", 1)

                    if parts and len(parts) == 2:
                        item_name, column_name = parts
                        item_name = item_name.strip()
                        column_name = column_name.strip()

                        # Find best matching item and column names
                        best_item = None
                        best_column = None

                        for q_item in self.question_items:
                            if (
                                q_item.lower() in item_name.lower()
                                or item_name.lower() in q_item.lower()
                            ):
                                best_item = q_item
                                break

                        for q_column in self.question_columns:
                            if (
                                q_column.lower() in column_name.lower()
                                or column_name.lower() in q_column.lower()
                            ):
                                best_column = q_column
                                break

                        if best_item and best_column:
                            if best_item not in restructured:
                                restructured[best_item] = {}

                            # Convert value to numeric if it's a string
                            numeric_value = value
                            if isinstance(value, str):
                                try:
                                    # Try to extract number from string
                                    match = re.search(
                                        r"-?\d+\.?\d*", value.replace(",", "")
                                    )
                                    if match:
                                        numeric_value = (
                                            float(match.group())
                                            if "." in match.group()
                                            else int(match.group())
                                        )
                                except (ValueError, AttributeError):
                                    numeric_value = value

                            restructured[best_item][best_column] = numeric_value

                if restructured:
                    proposed_data = {
                        "answer": restructured,
                        "comment": response.get("comment"),
                        "generated_tokens": response.get("generated_tokens"),
                    }
                    try:
                        self.response_model(**proposed_data)
                        if verbose:
                            print(
                                f"Successfully fixed by restructuring flat keys: {proposed_data}"
                            )
                        return proposed_data
                    except Exception as e:
                        if verbose:
                            print(f"Restructured response failed validation: {e}")

        # Strategy 2: If answer is a string, try to parse it as JSON or extract structured data
        if isinstance(answer, str):
            if verbose:
                print(f"Trying to parse string answer: {answer}")

            # Try JSON parsing first
            try:
                parsed_answer = json.loads(answer)
                proposed_data = {
                    "answer": parsed_answer,
                    "comment": response.get("comment"),
                    "generated_tokens": response.get("generated_tokens"),
                }
                try:
                    self.response_model(**proposed_data)
                    if verbose:
                        print(f"Successfully fixed by JSON parsing: {proposed_data}")
                    return proposed_data
                except Exception as e:
                    if verbose:
                        print(f"JSON parsed response failed validation: {e}")
            except json.JSONDecodeError:
                if verbose:
                    print("Failed to parse as JSON")

            # Try to extract numeric values using patterns
            # Look for patterns like "Item1: 7.5, Item2: 8.2"
            pairs = re.findall(r"([^:,]+):\s*([0-9.-]+)", answer)
            if pairs:
                extracted = {}
                for item_text, value_text in pairs:
                    item_text = item_text.strip()
                    try:
                        value = (
                            float(value_text) if "." in value_text else int(value_text)
                        )

                        # Find best matching item name
                        best_item = None
                        for q_item in self.question_items:
                            if (
                                q_item.lower() in item_text.lower()
                                or item_text.lower() in q_item.lower()
                            ):
                                best_item = q_item
                                break

                        if best_item:
                            if best_item not in extracted:
                                extracted[best_item] = {}
                            # For now, assign to first column - this is a limitation we might need to address
                            if self.question_columns:
                                extracted[best_item][self.question_columns[0]] = value
                    except ValueError:
                        continue

                if extracted:
                    proposed_data = {
                        "answer": extracted,
                        "comment": response.get("comment"),
                        "generated_tokens": response.get("generated_tokens"),
                    }
                    try:
                        self.response_model(**proposed_data)
                        if verbose:
                            print(
                                f"Successfully fixed by extracting pairs: {proposed_data}"
                            )
                        return proposed_data
                    except Exception as e:
                        if verbose:
                            print(f"Extracted pairs response failed validation: {e}")

        # Strategy 3: Try to convert string values to numeric in existing structure
        if isinstance(answer, dict):
            converted_answer = {}
            conversion_attempted = False

            for item_name, item_data in answer.items():
                if isinstance(item_data, dict):
                    converted_item = {}
                    for column_name, value in item_data.items():
                        if isinstance(value, str):
                            conversion_attempted = True
                            try:
                                # Try to extract number from string
                                match = re.search(
                                    r"-?\d+\.?\d*", value.replace(",", "")
                                )
                                if match:
                                    converted_value = (
                                        float(match.group())
                                        if "." in match.group()
                                        else int(match.group())
                                    )
                                    converted_item[column_name] = converted_value
                                else:
                                    converted_item[column_name] = value
                            except (ValueError, AttributeError):
                                converted_item[column_name] = value
                        else:
                            converted_item[column_name] = value
                    converted_answer[item_name] = converted_item
                else:
                    converted_answer[item_name] = item_data

            if conversion_attempted:
                proposed_data = {
                    "answer": converted_answer,
                    "comment": response.get("comment"),
                    "generated_tokens": response.get("generated_tokens"),
                }
                try:
                    self.response_model(**proposed_data)
                    if verbose:
                        print(
                            f"Successfully fixed by converting strings to numbers: {proposed_data}"
                        )
                    return proposed_data
                except Exception as e:
                    if verbose:
                        print(f"String conversion response failed validation: {e}")

        # If we got here, we couldn't fix the response
        if verbose:
            print("Could not fix matrix entry response, returning original")
        return response


class QuestionMatrixEntry(QuestionBase):
    """
    A question that presents a matrix/grid where multiple items are rated
    with numeric values across different columns.

    This question type allows respondents to provide numeric entries for each cell
    in a grid, where rows represent items to be rated and columns represent different
    scenarios or categories. It's useful for collecting quantitative assessments
    across multiple dimensions.

    Examples:
        >>> # Create a trust/satisfaction rating matrix
        >>> question = QuestionMatrixEntry(
        ...     question_name="ai_trust_matrix",
        ...     question_text="Rate your trust and satisfaction levels (0-10):",
        ...     question_items=["Trust level", "Satisfaction level"],
        ...     question_columns=["No AI Tools", "With AI Help", "AI Only"],
        ...     min_value=0,
        ...     max_value=10
        ... )
        >>> # The response is a nested dict: item -> column -> numeric value
        >>> response = {
        ...     "answer": {
        ...         "Trust level": {"No AI Tools": 7.5, "With AI Help": 8.2, "AI Only": 6.1},
        ...         "Satisfaction level": {"No AI Tools": 6.8, "With AI Help": 9.1, "AI Only": 7.3}
        ...     }
        ... }
    """

    question_type = "matrix_entry"
    question_text: str = QuestionTextDescriptor()
    question_items: List[str] = QuestionOptionsDescriptor()
    question_columns: List[str] = QuestionOptionsDescriptor()
    min_value: Optional[float] = NumericalOrNoneDescriptor()
    max_value: Optional[float] = NumericalOrNoneDescriptor()

    _response_model = None
    response_validator_class = MatrixEntryResponseValidator

    def __init__(
        self,
        question_name: str,
        question_text: str,
        question_items: List[str],
        question_columns: List[str],
        min_value: Optional[Union[int, float]] = None,
        max_value: Optional[Union[int, float]] = None,
        include_comment: bool = True,
        answering_instructions: Optional[str] = None,
        question_presentation: Optional[str] = None,
        permissive: bool = False,
    ):
        """
        Initialize a matrix entry question.

        Args:
            question_name: The name of the question
            question_text: The text of the question
            question_items: List of items to be rated (rows)
            question_columns: List of column headers (scenarios/categories)
            min_value: Optional minimum value for numeric entries
            max_value: Optional maximum value for numeric entries
            include_comment: Whether to include a comment field
            answering_instructions: Custom instructions template
            question_presentation: Custom presentation template
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
        self.question_columns = question_columns
        self.min_value = min_value
        self.max_value = max_value

        self.include_comment = include_comment
        self.answering_instructions = answering_instructions
        self.question_presentation = question_presentation
        self.permissive = permissive

    def create_response_model(self) -> Type[BaseModel]:
        """
        Returns the pydantic model for validating responses to this question.

        The model is dynamically created based on the question's configuration,
        including items, columns, numeric constraints, and permissiveness.
        """
        return create_matrix_entry_response(
            self.question_items,
            self.question_columns,
            self.min_value,
            self.max_value,
            self.permissive,
        )

    def _simulate_answer(self) -> dict:
        """
        Simulate a random valid answer for testing purposes.

        Returns:
            A valid simulated response with random numeric entries
        """
        min_val = self.min_value if self.min_value is not None else 0
        max_val = self.max_value if self.max_value is not None else 10

        answer = {}
        for item in self.question_items:
            answer[item] = {}
            for column in self.question_columns:
                # Generate random numeric value within constraints
                if isinstance(min_val, int) and isinstance(max_val, int):
                    value = random.randint(int(min_val), int(max_val))
                else:
                    value = round(random.uniform(float(min_val), float(max_val)), 2)
                answer[item][column] = value

        return {
            "answer": answer,
            "comment": "Sample matrix entry response",
        }

    @property
    def question_html_content(self) -> str:
        """
        Generate an HTML representation of the matrix entry question.

        Returns:
            HTML content string for rendering the question
        """
        template = Template(
            """
        <table class="matrix-entry-question">
            <tr>
                <th></th>
                {% for column in question_columns %}
                <th>{{ column }}</th>
                {% endfor %}
            </tr>
            {% for item in question_items %}
            <tr>
                <td><strong>{{ item }}</strong></td>
                {% for column in question_columns %}
                <td>
                    <input type="number"
                           name="{{ question_name }}_{{ item }}_{{ column }}"
                           id="{{ question_name }}_{{ item }}_{{ column }}"
                           {% if min_value is not none %}min="{{ min_value }}"{% endif %}
                           {% if max_value is not none %}max="{{ max_value }}"{% endif %}
                           step="0.1"
                           placeholder="Enter number">
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
            question_columns=self.question_columns,
            min_value=self.min_value,
            max_value=self.max_value,
        )

    @classmethod
    @inject_exception
    def example(cls) -> "QuestionMatrixEntry":
        """
        Return an example matrix entry question.

        Returns:
            An example QuestionMatrixEntry instance for AI tool trust ratings
        """
        return cls(
            question_name="ai_trust_satisfaction",
            question_text="Rate your trust and satisfaction levels (0-10) for different AI usage scenarios:",
            question_items=["Trust level", "Satisfaction level"],
            question_columns=["No AI Tools", "With AI Help", "AI Only"],
            min_value=0,
            max_value=10,
        )
