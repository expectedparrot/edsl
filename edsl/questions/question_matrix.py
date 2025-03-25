"""
question_matrix.py

Module implementing the matrix question type with Pydantic validation
"""

from __future__ import annotations
from typing import (
    Union,
    Optional,
    Dict,
    List,
    Any,
    Type,
    Literal
)
import random
import json
import re

from pydantic import BaseModel, Field, create_model, ValidationError, model_validator
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
    QuestionAnswerValidationError,
)


class MatrixResponseBase(BaseModel):
    """
    Base model for matrix question responses.
    
    Attributes:
        answer: A dictionary mapping each item to a selected option
        comment: Optional comment about the selections
        generated_tokens: Optional token usage data
    
    Examples:
        >>> # Valid response with two items
        >>> model = MatrixResponseBase(answer={"Item1": 1, "Item2": 2})
        >>> model.answer
        {'Item1': 1, 'Item2': 2}
        
        >>> # Valid response with a comment
        >>> model = MatrixResponseBase(
        ...     answer={"Item1": "Yes", "Item2": "No"},
        ...     comment="This is my reasoning"
        ... )
        >>> model.comment
        'This is my reasoning'
    """
    answer: Dict[str, Any]
    comment: Optional[str] = None
    generated_tokens: Optional[Any] = None


def create_matrix_response(
    question_items: List[str],
    question_options: List[Union[int, str, float]],
    permissive: bool = False,
) -> Type[BaseModel]:
    """
    Create a dynamic Pydantic model for matrix questions with appropriate validation.
    
    Args:
        question_items: List of items that need responses
        question_options: List of allowed options for each item
        permissive: If True, allows any values and additional items
        
    Returns:
        A Pydantic model class for validating matrix responses
        
    Examples:
        >>> # Create a model for a 2x3 matrix
        >>> Model = create_matrix_response(
        ...     ["Item1", "Item2"], 
        ...     [1, 2, 3]
        ... )
        >>> # Valid response
        >>> response = Model(answer={"Item1": 1, "Item2": 2})
        >>> isinstance(response.answer, BaseModel)
        True
        >>> response.answer.Item1
        1
        >>> response.answer.Item2
        2
        
        >>> # Invalid: missing an item
        >>> try:
        ...     Model(answer={"Item1": 1})
        ... except Exception:
        ...     print("Validation error occurred")
        Validation error occurred
        
        >>> # Invalid: invalid option value
        >>> try:
        ...     Model(answer={"Item1": 4, "Item2": 2})
        ... except Exception:
        ...     print("Validation error occurred")
        Validation error occurred
    """
    # Convert question_options to a tuple for Literal type
    option_tuple = tuple(question_options)
    
    # If non-permissive, build a Literal for each valid option
    # e.g. Literal[1,2,3] or Literal["Yes","No"] or a mix
    if not permissive:
        # If question_options is empty (edge case), fall back to 'Any'
        if question_options:
            AllowedOptions = Literal[option_tuple]  # type: ignore
        else:
            AllowedOptions = Any
    else:
        # Permissive => let each item be anything
        AllowedOptions = Any

    # Build field definitions for the answer submodel
    field_definitions = {}
    for item in question_items:
        field_definitions[item] = (AllowedOptions, Field(...))  # required field

    # Dynamically create the submodel
    MatrixAnswerSubModel = create_model(
        "MatrixAnswerSubModel",
        __base__=BaseModel,
        **field_definitions
    )

    # Create the full response model with custom validation
    class MatrixResponse(MatrixResponseBase):
        """
        Model for matrix question responses with validation for specific items and options.
        """
        answer: MatrixAnswerSubModel  # Use the dynamically created submodel
        
        @model_validator(mode='after')
        def validate_matrix_constraints(self):
            """
            Validates that:
            1. All required items have responses
            2. All responses are valid options
            3. No unexpected items are included (unless permissive)
            """
            matrix_answer = self.answer.model_dump()
            
            # Check that all required items have responses
            missing_items = [item for item in question_items if item not in matrix_answer]
            if missing_items and not permissive:
                missing_str = ", ".join(missing_items)
                validation_error = ValidationError.from_exception_data(
                    title='MatrixResponse',
                    line_errors=[{
                        'type': 'value_error',
                        'loc': ('answer',),
                        'msg': f'Missing responses for items: {missing_str}',
                        'input': matrix_answer,
                        'ctx': {'missing_items': missing_items}
                    }]
                )
                raise QuestionAnswerValidationError(
                    message=f"Missing responses for items: {missing_str}",
                    data=self.model_dump(),
                    model=self.__class__,
                    pydantic_error=validation_error
                )
            
            # Check that all responses are valid options
            if not permissive:
                invalid_items = {}
                for item, value in matrix_answer.items():
                    if value not in option_tuple:
                        invalid_items[item] = value
                
                if invalid_items:
                    items_str = ", ".join(f"{k}: {v}" for k, v in invalid_items.items())
                    validation_error = ValidationError.from_exception_data(
                        title='MatrixResponse',
                        line_errors=[{
                            'type': 'value_error',
                            'loc': ('answer',),
                            'msg': f'Invalid options selected: {items_str}',
                            'input': matrix_answer,
                            'ctx': {'invalid_items': invalid_items, 'allowed_options': option_tuple}
                        }]
                    )
                    raise QuestionAnswerValidationError(
                        message=f"Invalid options selected: {items_str}. Allowed options: {option_tuple}",
                        data=self.model_dump(),
                        model=self.__class__,
                        pydantic_error=validation_error
                    )
            
            return self

        class Config:
            # If permissive=True, allow extra fields in the answer dict
            extra = "allow" if permissive else "forbid"
            
            @staticmethod
            def json_schema_extra(schema: dict, model: BaseModel) -> None:
                # Add the options to the schema for better documentation
                if "properties" in schema and "answer" in schema["properties"]:
                    schema["properties"]["answer"]["description"] = "Matrix responses for each item"
                    if "properties" in schema["properties"]["answer"]:
                        for _, prop in schema["properties"]["answer"]["properties"].items():
                            prop["enum"] = list(question_options)

    return MatrixResponse


class MatrixResponseValidator(ResponseValidatorABC):
    """
    Validator for matrix question responses that attempts to fix invalid responses.
    
    This validator tries multiple approaches to recover valid matrix responses from
    malformed inputs, including JSON parsing, remapping numeric keys, and extracting
    structured data from text.
    """
    required_params = ["question_items", "question_options", "permissive"]

    valid_examples = [
        (
            {"answer": {"Item1": 1, "Item2": 2}},
            {
                "question_items": ["Item1", "Item2"],
                "question_options": [1, 2, 3],
                "permissive": False
            },
        ),
        (
            {"answer": {"Item1": "Yes", "Item2": "No"}},
            {
                "question_items": ["Item1", "Item2"],
                "question_options": ["Yes", "No", "Maybe"],
                "permissive": False
            },
        ),
    ]

    invalid_examples = [
        (
            {"answer": {"Item1": 1}},
            {
                "question_items": ["Item1", "Item2"],
                "question_options": [1, 2, 3],
                "permissive": False
            },
            "Missing responses for items",
        ),
        (
            {"answer": {"Item1": 4, "Item2": 5}},
            {
                "question_items": ["Item1", "Item2"],
                "question_options": [1, 2, 3],
                "permissive": False
            },
            "Invalid options selected",
        ),
    ]

    def fix(self, response, verbose=False):
        """
        Attempts to fix an invalid matrix response by trying multiple parsing strategies.
        
        Args:
            response: The invalid response to fix
            verbose: Whether to print verbose debugging information
            
        Returns:
            A fixed response dict if fixable, otherwise the original response
        """
        if verbose:
            print(f"Fixing matrix response: {response}")
        
        # If response doesn't have an answer field, nothing to do
        if "answer" not in response:
            if verbose:
                print("Response has no answer field, cannot fix")
            return response
            
        # Strategy 1: If we have generated_tokens, try to parse them as JSON
        if "generated_tokens" in response and response["generated_tokens"]:
            try:
                # Try to parse generated_tokens as JSON
                tokens_text = str(response["generated_tokens"])
                json_match = re.search(r'\{.*\}', tokens_text, re.DOTALL)
                
                if json_match:
                    json_str = json_match.group(0)
                    fixed = json.loads(json_str)
                    
                    if isinstance(fixed, dict):
                        # Map numeric keys to question items if needed
                        if all(str(k).isdigit() for k in fixed.keys()):
                            if verbose:
                                print(f"JSON extraction found numeric keys: {fixed}")
                                print(f"Question items: {self.question_items}")
                                print(f"Question options: {self.question_options}")
                            
                            # Special handling for case when numeric keys directly represent option indices
                            # This is the case we're trying to fix: {"0": 1, "1": 3, "2": 0} maps to options at those indices
                            direct_mapped_answer = {}
                            if verbose:
                                print(f"Attempting to map numeric key/value format in JSON: {fixed}")
                                
                            for idx, item in enumerate(self.question_items):
                                if str(idx) in fixed:
                                    # Get the option index directly from the value
                                    option_idx = fixed[str(idx)]
                                    
                                    # Convert to int if needed
                                    if isinstance(option_idx, str) and option_idx.isdigit():
                                        option_idx = int(option_idx)
                                    
                                    if verbose:
                                        print(f"Item {item} at index {idx} maps to value {option_idx}")
                                        
                                    if isinstance(option_idx, (int, float)) and 0 <= option_idx < len(self.question_options):
                                        direct_mapped_answer[item] = self.question_options[option_idx]
                                        if verbose:
                                            print(f"Mapped option_idx {option_idx} to {self.question_options[option_idx]}")
                            
                            if direct_mapped_answer and len(direct_mapped_answer) == len(self.question_items):
                                proposed_data = {
                                    "answer": direct_mapped_answer,
                                    "comment": response.get("comment"),
                                    "generated_tokens": response.get("generated_tokens")
                                }
                                if verbose:
                                    print(f"Created direct option mapping from JSON: {proposed_data}")
                                try:
                                    self.response_model(**proposed_data)
                                    if verbose:
                                        print(f"Successfully fixed with direct option mapping from JSON: {proposed_data}")
                                    return proposed_data
                                except Exception as e:
                                    if verbose:
                                        print(f"Direct option mapping from JSON failed validation: {e}")
                            
                            # Try the standard approach as well
                            mapped_answer = {}
                            for idx, item in enumerate(self.question_items):
                                if str(idx) in fixed:
                                    # Get the value (column index) from the response
                                    value_idx = fixed[str(idx)]
                                    
                                    # Convert to int if it's a digit string
                                    if isinstance(value_idx, str) and value_idx.isdigit():
                                        value_idx = int(value_idx)
                                    
                                    # Convert column index to actual option value
                                    if isinstance(value_idx, (int, float)) and 0 <= value_idx < len(self.question_options):
                                        option_value = self.question_options[value_idx]
                                        mapped_answer[item] = option_value
                                    else:
                                        # If the value is already a valid option, use it directly
                                        if value_idx in self.question_options:
                                            mapped_answer[item] = value_idx
                                        else:
                                            # Last resort - try to use it as a direct value even if not in options
                                            mapped_answer[item] = value_idx
                                    
                            if mapped_answer and (len(mapped_answer) == len(self.question_items) or self.permissive):
                                proposed_data = {
                                    "answer": mapped_answer,
                                    "comment": response.get("comment"),
                                    "generated_tokens": response.get("generated_tokens")
                                }
                                try:
                                    # Validate the fixed response
                                    self.response_model(**proposed_data)
                                    if verbose:
                                        print(f"Successfully fixed by parsing JSON: {proposed_data}")
                                    return proposed_data
                                except Exception as e:
                                    if verbose:
                                        print(f"Fixed response failed validation: {e}")
                                    
                                # Try again with string values for all options
                                text_mapped_answer = {}
                                for item_name, option_value in mapped_answer.items():
                                    text_mapped_answer[item_name] = str(option_value)
                                    
                                proposed_data = {
                                    "answer": text_mapped_answer,
                                    "comment": response.get("comment"),
                                    "generated_tokens": response.get("generated_tokens")
                                }
                                try:
                                    self.response_model(**proposed_data)
                                    if verbose:
                                        print(f"Successfully fixed with string conversion from JSON: {proposed_data}")
                                    return proposed_data
                                except Exception as e:
                                    if verbose:
                                        print(f"String conversion from JSON failed validation: {e}")
                        else:
                            # The JSON already has string keys, use directly
                            proposed_data = {
                                "answer": fixed,
                                "comment": response.get("comment"),
                                "generated_tokens": response.get("generated_tokens")
                            }
                            try:
                                self.response_model(**proposed_data)
                                if verbose:
                                    print(f"Successfully fixed by direct JSON: {proposed_data}")
                                return proposed_data
                            except Exception as e:
                                if verbose:
                                    print(f"Fixed response failed validation: {e}")
                                
                                # If validation failed, check if we need to map string keys to item names
                                # This handles cases where the model responded with something like {"Row 0": 1, "Row 1": 2}
                                # instead of using the exact item names
                                item_map = {}
                                for item in self.question_items:
                                    # Create various forms of the item name that might appear in responses
                                    item_variants = [
                                        item.lower(),
                                        item.upper(),
                                        item.strip(),
                                        f"Row {self.question_items.index(item)}",
                                        f"Item {self.question_items.index(item)}",
                                        f"{self.question_items.index(item)}"
                                    ]
                                    for key in fixed.keys():
                                        if isinstance(key, str):
                                            key_lower = key.lower().strip()
                                            if key_lower in item_variants or item.lower() in key_lower:
                                                item_map[key] = item
                                
                                if item_map:
                                    mapped_answer = {}
                                    for key, value in fixed.items():
                                        if key in item_map:
                                            # Handle both numeric indices and direct values
                                            if isinstance(value, (int, float)) and 0 <= value < len(self.question_options):
                                                mapped_answer[item_map[key]] = self.question_options[value]
                                            else:
                                                mapped_answer[item_map[key]] = value
                                    
                                    if mapped_answer:
                                        proposed_data = {
                                            "answer": mapped_answer,
                                            "comment": response.get("comment"),
                                            "generated_tokens": response.get("generated_tokens")
                                        }
                                        try:
                                            self.response_model(**proposed_data)
                                            if verbose:
                                                print(f"Successfully fixed by mapping item names: {proposed_data}")
                                            return proposed_data
                                        except Exception as e:
                                            if verbose:
                                                print(f"Item-mapped response failed validation: {e}")
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
                if verbose:
                    print(f"JSON parsing failed: {e}")
                # Continue to other strategies
        
        # Strategy 2: If answer uses numeric keys, map them to question items
        if isinstance(response.get("answer"), dict):
            answer_dict = response["answer"]
            
            if all(str(k).isdigit() for k in answer_dict.keys()):
                if verbose:
                    print(f"Processing answer with numeric keys: {answer_dict}")
                    print(f"Question items: {self.question_items}")
                    print(f"Question options: {self.question_options}")
                
                mapped_answer = {}
                for idx, item in enumerate(self.question_items):
                    if str(idx) in answer_dict:
                        # Get the value (column index) from the response
                        value_idx = answer_dict[str(idx)]
                        
                        # Convert to int if it's a digit string
                        if isinstance(value_idx, str) and value_idx.isdigit():
                            value_idx = int(value_idx)
                        
                        if verbose:
                            print(f"Processing item {item} at index {idx}, value_idx={value_idx}")
                        
                        # Convert column index to actual option value
                        if isinstance(value_idx, (int, float)) and 0 <= value_idx < len(self.question_options):
                            option_value = self.question_options[value_idx]
                            mapped_answer[item] = option_value
                            if verbose:
                                print(f"Mapped column index {value_idx} to option '{option_value}'")
                        else:
                            # If the value is already a valid option, use it directly
                            if value_idx in self.question_options:
                                mapped_answer[item] = value_idx
                                if verbose:
                                    print(f"Used direct option value '{value_idx}'")
                            else:
                                # Last resort - try to use it as a direct value even if not in options
                                # (this helps with permissive mode)
                                mapped_answer[item] = value_idx
                                if verbose:
                                    print(f"Used non-option value '{value_idx}' as direct value")
                
                if mapped_answer and len(mapped_answer) == len(self.question_items):
                    if verbose:
                        print(f"Created complete mapped answer: {mapped_answer}")
                    
                    proposed_data = {
                        "answer": mapped_answer,
                        "comment": response.get("comment"),
                        "generated_tokens": response.get("generated_tokens")
                    }
                    try:
                        self.response_model(**proposed_data)
                        if verbose:
                            print(f"Successfully fixed by mapping numeric keys: {proposed_data}")
                        return proposed_data
                    except Exception as e:
                        if verbose:
                            print(f"Fixed response failed validation: {e}")
                    
                    # Try again with string values for the options
                    text_mapped_answer = {}
                    for item_name, option_value in mapped_answer.items():
                        text_mapped_answer[item_name] = str(option_value)
                        
                    proposed_data = {
                        "answer": text_mapped_answer,
                        "comment": response.get("comment"),
                        "generated_tokens": response.get("generated_tokens")
                    }
                    try:
                        self.response_model(**proposed_data)
                        if verbose:
                            print(f"Successfully fixed with string conversion: {proposed_data}")
                        return proposed_data
                    except Exception as e:
                        if verbose:
                            print(f"String conversion failed validation: {e}")
                            
                # Special handling for case when numeric keys directly represent option indices
                # This is the case we're trying to fix: {"0": 1, "1": 3, "2": 0} maps to options at those indices
                direct_mapped_answer = {}
                if verbose:
                    print(f"Attempting to map numeric key/value format in answer: {answer_dict}")
                
                for idx, item in enumerate(self.question_items):
                    if str(idx) in answer_dict:
                        # Get the option index directly from the value
                        option_idx = answer_dict[str(idx)]
                        
                        # Convert to int if needed
                        if isinstance(option_idx, str) and option_idx.isdigit():
                            option_idx = int(option_idx)
                        
                        if verbose:
                            print(f"Item {item} at index {idx} maps to value {option_idx}")
                            
                        if isinstance(option_idx, (int, float)) and 0 <= option_idx < len(self.question_options):
                            direct_mapped_answer[item] = self.question_options[option_idx]
                            if verbose:
                                print(f"Mapped option_idx {option_idx} to {self.question_options[option_idx]}")
                
                if direct_mapped_answer and len(direct_mapped_answer) == len(self.question_items):
                    proposed_data = {
                        "answer": direct_mapped_answer,
                        "comment": response.get("comment"),
                        "generated_tokens": response.get("generated_tokens")
                    }
                    if verbose:
                        print(f"Created direct option mapping: {proposed_data}")
                    try:
                        self.response_model(**proposed_data)
                        if verbose:
                            print(f"Successfully fixed with direct option mapping: {proposed_data}")
                        return proposed_data
                    except Exception as e:
                        if verbose:
                            print(f"Direct option mapping failed validation: {e}")
        
        # Strategy 3: If answer is a string, try to extract a structured response
        if isinstance(response.get("answer"), str):
            answer_text = response["answer"]
            
            # Try to extract item-option pairs using regex
            pairs = re.findall(r'([^:,]+):\s*([^,]+)', answer_text)
            if pairs:
                extracted = {}
                for item, option in pairs:
                    item = item.strip()
                    option = option.strip()
                    
                    # Match the item name with the closest question item
                    best_match = None
                    for q_item in self.question_items:
                        if q_item.lower() in item.lower():
                            best_match = q_item
                            break
                    
                    if best_match:
                        # Try to match the option with question options
                        matched_option = None
                        for q_option in self.question_options:
                            q_option_str = str(q_option)
                            if q_option_str == option or q_option_str in option:
                                matched_option = q_option
                                break
                        
                        if matched_option is not None:
                            extracted[best_match] = matched_option
                
                if extracted and (len(extracted) == len(self.question_items) or self.permissive):
                    proposed_data = {
                        "answer": extracted,
                        "comment": response.get("comment"),
                        "generated_tokens": response.get("generated_tokens")
                    }
                    try:
                        self.response_model(**proposed_data)
                        if verbose:
                            print(f"Successfully fixed by extracting pairs: {proposed_data}")
                        return proposed_data
                    except Exception as e:
                        if verbose:
                            print(f"Fixed response failed validation: {e}")
        
        # If we got here, we couldn't fix the response
        if verbose:
            print("Could not fix matrix response, returning original")
        return response


class QuestionMatrix(QuestionBase):
    """
    A question that presents a matrix/grid where multiple items are rated
    or selected from the same set of options.
    
    This question type allows respondents to provide an answer for each row
    in a grid, selecting from the same set of options for each row. It's often
    used for Likert scales, ratings grids, or any scenario where multiple items
    need to be rated using the same scale.
    
    Examples:
        >>> # Create a happiness rating matrix
        >>> question = QuestionMatrix(
        ...     question_name="happiness_matrix",
        ...     question_text="Rate your happiness with each aspect:",
        ...     question_items=["Work", "Family", "Social life"],
        ...     question_options=[1, 2, 3, 4, 5],
        ...     option_labels={1: "Very unhappy", 3: "Neutral", 5: "Very happy"}
        ... )
        >>> # The response is a dict matching each item to a rating
        >>> response = {"answer": {"Work": 4, "Family": 5, "Social life": 3}}
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
            question_items: List of items to be rated or answered (rows)
            question_options: Possible answer options for each item (columns)
            option_labels: Optional mapping of options to labels (e.g. {1: "Sad", 5: "Happy"})
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
        self.question_options = question_options
        self.option_labels = option_labels or {}

        self.include_comment = include_comment
        self.answering_instructions = answering_instructions
        self.question_presentation = question_presentation
        self.permissive = permissive

    def create_response_model(self) -> Type[BaseModel]:
        """
        Returns the pydantic model for validating responses to this question.
        
        The model is dynamically created based on the question's configuration,
        including allowed items, options, and permissiveness.
        """
        return create_matrix_response(
            self.question_items,
            self.question_options,
            self.permissive
        )

    def _simulate_answer(self) -> dict:
        """
        Simulate a random valid answer for testing purposes.
        
        Returns:
            A valid simulated response with random selections
        """
        return {
            "answer": {
                item: random.choice(self.question_options)
                for item in self.question_items
            },
            "comment": "Sample matrix response"
        }

    @property
    def question_html_content(self) -> str:
        """
        Generate an HTML representation of the matrix question.
        
        Returns:
            HTML content string for rendering the question
        """
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
        """
        Return an example matrix question.
        
        Returns:
            An example QuestionMatrix instance for happiness ratings by family size
        """
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