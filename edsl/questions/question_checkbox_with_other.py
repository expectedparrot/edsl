from __future__ import annotations
from typing import Any, Optional, List, Union, TYPE_CHECKING

import random
from jinja2 import Template
from pydantic import BaseModel, Field, model_validator, ValidationError
from typing import Literal, Annotated

from .exceptions import QuestionAnswerValidationError
from ..scenarios import Scenario

from .question_base import QuestionBase
from .descriptors import (
    IntegerDescriptor,
    QuestionOptionsDescriptor,
    OtherOptionTextDescriptor,
)
from .decorators import inject_exception
from .question_check_box import (
    CheckboxResponse,
    CheckBoxResponseValidator,
)

if TYPE_CHECKING:
    pass


class CheckboxWithOtherResponse(BaseModel):
    """
    Base Pydantic model for validating checkbox with other responses.

    This model defines the structure and validation rules for responses to
    checkbox questions that include an "Other" option, allowing custom responses.

    Attributes:
        answer: List of selected choices (may include "Other: X" entries)
        comment: Optional comment provided with the answer
        generated_tokens: Optional raw LLM output for token tracking

    Examples:
        >>> response = CheckboxWithOtherResponse(answer=["Apple", "Banana"])
        >>> response.answer
        ['Apple', 'Banana']

        >>> response = CheckboxWithOtherResponse(answer=["Apple", "Other: Mango"])
        >>> response.answer
        ['Apple', 'Other: Mango']
    """

    answer: List[Any]
    comment: Optional[str] = None
    generated_tokens: Optional[Any] = None


def create_checkbox_with_other_response_model(
    choices: list,
    min_selections: Optional[int] = None,
    max_selections: Optional[int] = None,
    other_option_text: str = "Other",
    permissive: bool = False,
):
    """
    Dynamically create a CheckboxWithOtherResponse model with a predefined list of choices.

    This function creates a customized Pydantic model for checkbox questions with "Other"
    option that validates both the format of the response and any constraints on selection count.

    Args:
        choices: A list of allowed values for the answer field
        min_selections: Optional minimum number of selections required
        max_selections: Optional maximum number of selections allowed
        other_option_text: The text used for the "Other" option (e.g., "Other", "Something else")
        permissive: If True, constraints are not enforced

    Returns:
        A new Pydantic model class with appropriate validation

    Examples:
        >>> choices = ["Apple", "Banana", "Cherry", "Other"]
        >>> Model = create_checkbox_with_other_response_model(
        ...     choices=choices,
        ...     min_selections=1,
        ...     max_selections=3,
        ...     other_option_text="Other"
        ... )
        >>> response = Model(answer=["Apple", "Other: Mango"])
        >>> response.answer
        ['Apple', 'Other: Mango']
    """

    def is_valid_choice(choice, valid_choices, other_option_text):
        """Check if a choice is valid (either in the list or matches Other: X pattern)."""
        if choice in valid_choices:
            return True
        # Check for "Other: X" pattern
        choice_str = str(choice)
        choice_lower = choice_str.lower()
        other_lower = other_option_text.lower()
        if choice_lower.startswith(other_lower):
            remaining = choice_str[len(other_option_text) :]
            if remaining.strip().startswith(":"):
                return True
        # Also check for generic "Other: X" pattern
        if choice_lower.startswith("other"):
            remaining = choice_str[5:]  # len("other") = 5
            if remaining.strip().startswith(":"):
                return True
        return False

    if permissive:

        class PermissiveCheckboxWithOtherResponse(CheckboxWithOtherResponse):
            """Checkbox with other response model with permissive validation."""

            @model_validator(mode="after")
            def validate_choices(self):
                """Validate that each selected choice is valid or matches Other: X pattern."""
                # In permissive mode, we still validate "Other: X" pattern but don't enforce constraints
                return self

        return PermissiveCheckboxWithOtherResponse
    else:

        class ConstrainedCheckboxWithOtherResponse(CheckboxWithOtherResponse):
            """Checkbox with other response model with both choice and count constraints."""

            @model_validator(mode="after")
            def validate_selection_count(self):
                """Validate that the number of selections meets constraints and choices are valid."""
                if min_selections is not None and len(self.answer) < min_selections:
                    validation_error = ValidationError.from_exception_data(
                        title="CheckboxWithOtherResponse",
                        line_errors=[
                            {
                                "type": "value_error",
                                "loc": ("answer",),
                                "msg": f"Must select at least {min_selections} option(s)",
                                "input": self.answer,
                                "ctx": {"error": "Too few selections"},
                            }
                        ],
                    )
                    raise QuestionAnswerValidationError(
                        message=f"Must select at least {min_selections} option(s), got {len(self.answer)}",
                        data=self.model_dump(),
                        model=self.__class__,
                        pydantic_error=validation_error,
                    )

                if max_selections is not None and len(self.answer) > max_selections:
                    validation_error = ValidationError.from_exception_data(
                        title="CheckboxWithOtherResponse",
                        line_errors=[
                            {
                                "type": "value_error",
                                "loc": ("answer",),
                                "msg": f"Must select at most {max_selections} option(s)",
                                "input": self.answer,
                                "ctx": {"error": "Too many selections"},
                            }
                        ],
                    )
                    raise QuestionAnswerValidationError(
                        message=f"Must select at most {max_selections} option(s), got {len(self.answer)}",
                        data=self.model_dump(),
                        model=self.__class__,
                        pydantic_error=validation_error,
                    )

                # Validate that each choice is valid or matches "Other: X" pattern
                for choice in self.answer:
                    if not is_valid_choice(choice, choices, other_option_text):
                        validation_error = ValidationError.from_exception_data(
                            title="CheckboxWithOtherResponse",
                            line_errors=[
                                {
                                    "type": "value_error",
                                    "loc": ("answer",),
                                    "msg": f"Invalid choice: {choice}. Must be one of: {choices} or '{other_option_text}: [your response]'",
                                    "input": choice,
                                    "ctx": {"error": "Invalid choice"},
                                }
                            ],
                        )
                        raise QuestionAnswerValidationError(
                            message=f"Invalid choice: {choice}. Must be one of: {choices} or '{other_option_text}: [your response]'",
                            data=self.model_dump(),
                            model=self.__class__,
                            pydantic_error=validation_error,
                        )

                return self

        return ConstrainedCheckboxWithOtherResponse


class CheckboxWithOtherResponseValidator(CheckBoxResponseValidator):
    """
    Validator for checkbox with "other" question responses.

    This class extends the CheckBoxResponseValidator to handle
    the case where a user selects "Other" and provides a custom response
    within the list of selections.

    Attributes:
        required_params: List of required parameters for validation.
        valid_examples: Examples of valid responses for testing.
        invalid_examples: Examples of invalid responses for testing.

    Examples:
        >>> from edsl.questions import QuestionCheckboxWithOther
        >>> q = QuestionCheckboxWithOther(
        ...     question_name="fruits",
        ...     question_text="Which fruits do you like?",
        ...     question_options=["Apple", "Banana", "Cherry"],
        ...     other_option_text="Other"
        ... )
        >>> validator = q.response_validator
        >>> result = validator.validate({"answer": ["Apple", "Banana"]})
        >>> sorted(result["answer"])
        ['Apple', 'Banana']
        >>> # Direct "Other: X" format in list - full string is kept
        >>> result = validator.validate({"answer": ["Apple", "Other: Mango"]})
        >>> "Other: Mango" in result["answer"]
        True
    """

    required_params = [
        "question_options",
        "min_selections",
        "max_selections",
        "use_code",
        "other_option_text",
        "permissive",
    ]

    def __init__(self, **kwargs):
        """
        Initialize the validator.

        Ensures that other_option_text is added to the question_options.
        """
        super().__init__(**kwargs)

        # Make sure other_option_text is always in the list of valid options
        question_options = list(self.question_options)
        if self.other_option_text not in question_options:
            question_options.append(self.other_option_text)
        # Also add "Other" for backward compatibility
        if "Other" not in question_options:
            question_options.append("Other")
        self.question_options = question_options

    def _is_other_pattern(self, item):
        """Check if an item matches the 'Other: X' pattern."""
        item_str = str(item)
        item_lower = item_str.lower()
        other_lower = self.other_option_text.lower()

        # Check if it starts with other_option_text (case-insensitive)
        if item_lower.startswith(other_lower):
            remaining = item_str[len(self.other_option_text) :]
            if remaining.strip().startswith(":"):
                return True
        # Also check for generic "Other: X" pattern
        if item_lower.startswith("other"):
            remaining = item_str[5:]  # len("other") = 5
            if remaining.strip().startswith(":"):
                return True
        return False

    def validate(self, response_dict, verbose=False):
        """
        Validate the response according to the schema.

        This overrides the parent validate method to handle the "Other" option specially.
        If any item in the answer list is in the format "{other_option_text}: X", it keeps
        the full string as-is.

        Parameters:
            response_dict: The response to validate
            verbose: Whether to print debug information

        Returns:
            A validated response dict with the full answer strings preserved
        """
        # Create a copy to avoid modifying the original
        response_dict = response_dict.copy()

        # Check if answer is a list and contains "Other: X" patterns
        answer = response_dict.get("answer", [])
        has_other_pattern = False
        if isinstance(answer, list):
            has_other_pattern = any(self._is_other_pattern(item) for item in answer)
            if has_other_pattern and verbose:
                print(f"Detected '{self.other_option_text}: X' format in list items")

        # Try to validate with the parent validator
        try:
            validated_response = super().validate(response_dict, verbose)
            return validated_response
        except Exception as e:
            # Only accept special handling if there's an "Other: X" pattern
            # AND the only validation failure is that "Other: X" isn't in the options list
            if isinstance(answer, list) and has_other_pattern:
                # Check if all items are valid (either in options or match Other pattern)
                all_valid = True
                for item in answer:
                    if item not in self.question_options and not self._is_other_pattern(
                        item
                    ):
                        all_valid = False
                        break

                # Also check min/max constraints
                if all_valid:
                    if self.min_selections is not None and len(answer) < self.min_selections:
                        all_valid = False
                    if self.max_selections is not None and len(answer) > self.max_selections:
                        all_valid = False

                if all_valid:
                    if verbose:
                        print(
                            f"Validation failed but answer has valid Other pattern and meets constraints, accepting: {answer}"
                        )
                    validated_response = {
                        "answer": answer,
                        "comment": response_dict.get("comment"),
                        "generated_tokens": response_dict.get("generated_tokens"),
                    }
                    return validated_response

            # Otherwise, re-raise the exception
            raise

    def fix(self, response, verbose=False):
        """
        Attempt to fix an invalid checkbox with other response.

        Extends the CheckBoxResponseValidator fix method to also
        handle "{other_option_text}: X" format responses by keeping the full string.

        Parameters:
            response: The invalid response to fix
            verbose: Whether to print debug information

        Returns:
            A fixed response dict if possible, otherwise the original response
        """
        if verbose:
            print("Invalid response of QuestionCheckboxWithOther was: ", response)

        # If answer is a list, check each item for "Other: X" pattern
        answer = response.get("answer", [])
        if isinstance(answer, list):
            fixed_list = []
            needs_fixing = False
            for item in answer:
                if self._is_other_pattern(item):
                    # Keep the full "Other: X" string
                    fixed_list.append(item)
                    if verbose:
                        print(
                            f"Keeping '{self.other_option_text}: X' format item: {item}"
                        )
                elif item in self.question_options:
                    fixed_list.append(item)
                elif self.use_code and isinstance(item, int):
                    if 0 <= item < len(self.question_options):
                        fixed_list.append(item)
                    else:
                        needs_fixing = True
                else:
                    needs_fixing = True

            if not needs_fixing and fixed_list:
                proposed_data = {
                    "answer": fixed_list,
                    "comment": response.get("comment"),
                    "generated_tokens": response.get("generated_tokens"),
                }
                try:
                    # Try to validate
                    return self.validate(proposed_data, verbose=verbose)
                except Exception:
                    pass

        # If answer is a string, check if it's "Other: X" pattern
        if isinstance(answer, str):
            if self._is_other_pattern(answer):
                proposed_data = {
                    "answer": [answer],
                    "comment": response.get("comment"),
                    "generated_tokens": response.get("generated_tokens"),
                }
                try:
                    return self.validate(proposed_data, verbose=verbose)
                except Exception:
                    pass

        # Fall back to parent fix method
        return super().fix(response, verbose)

    valid_examples = [
        (
            {"answer": ["Good", "Great"]},
            {
                "question_options": ["Good", "Great", "OK", "Bad"],
                "other_option_text": "Other",
            },
        ),
        (
            {"answer": ["Good", "Other: Fantastic"]},
            {
                "question_options": ["Good", "Great", "OK", "Bad"],
                "other_option_text": "Other",
            },
        ),
    ]

    invalid_examples = [
        (
            {"answer": ["Terrible"]},
            {
                "question_options": ["Good", "Great", "OK", "Bad"],
                "other_option_text": "Other",
            },
            "Invalid choice",
        ),
    ]


class QuestionCheckboxWithOther(QuestionBase):
    """
    A question that prompts the agent to select multiple options from a list or specify "Other".

    QuestionCheckboxWithOther extends QuestionCheckBox to include an "Other" option
    that allows the agent to provide a custom response when none of the predefined options
    are suitable. This is useful for surveys and open-ended questions where
    you want to capture multiple responses that may not fit into predefined categories.

    Key Features:
    - All features of QuestionCheckBox
    - Additional "Other" option that allows custom responses in the selection list
    - Customizable text for the "Other" option
    - Supports "Other: X" format where the full string is stored in the answer list
    - Min/max selection constraints still apply to total count

    Technical Details:
    - Uses extended Pydantic models for validation
    - Preserves all functionality of QuestionCheckBox
    - Full answer strings (e.g., ["Apple", "Other: Mango"]) are stored in the answer field
    - Validator handles "Other: X" format by keeping the full string in the list

    Examples:
        Basic usage:

        >>> q = QuestionCheckboxWithOther(
        ...     question_name="fruits",
        ...     question_text="Which fruits do you like?",
        ...     question_options=["Apple", "Banana", "Cherry", "Durian"]
        ... )
        >>> q.question_type
        'checkbox_with_other'

        Custom "Other" option text:

        >>> q = QuestionCheckboxWithOther(
        ...     question_name="fruits",
        ...     question_text="Which fruits do you like?",
        ...     question_options=["Apple", "Banana", "Cherry"],
        ...     other_option_text="Something else (please specify)"
        ... )

        With selection constraints:

        >>> q = QuestionCheckboxWithOther(
        ...     question_name="toppings",
        ...     question_text="Select 2-4 pizza toppings:",
        ...     question_options=["Cheese", "Pepperoni", "Mushroom", "Onion"],
        ...     min_selections=2,
        ...     max_selections=4
        ... )
    """

    question_type = "checkbox_with_other"
    purpose = "When options are known but you want to allow for custom responses with multiple selections"
    question_options: Union[list[str], list[list], list[float], list[int]] = (
        QuestionOptionsDescriptor()
    )
    other_option_text: str = OtherOptionTextDescriptor()
    min_selections = IntegerDescriptor(none_allowed=True)
    max_selections = IntegerDescriptor(none_allowed=True)

    _response_model = None
    response_validator_class = CheckboxWithOtherResponseValidator

    def __init__(
        self,
        question_name: str,
        question_text: str,
        question_options: Union[list[str], list[list], list[float], list[int]],
        min_selections: Optional[int] = None,
        max_selections: Optional[int] = None,
        include_comment: bool = True,
        use_code: bool = False,
        question_presentation: Optional[str] = None,
        answering_instructions: Optional[str] = None,
        permissive: bool = False,
        other_option_text: str = "Other",
    ):
        """
        Initialize a new checkbox with "Other" question.

        Parameters
        ----------
        question_name : str
            The name of the question, used as an identifier. Must be a valid Python variable name.

        question_text : str
            The actual text of the question to be asked.

        question_options : Union[list[str], list[list], list[float], list[int]]
            The list of options the agent can select from. The "Other" option will be
            automatically added to this list.

        min_selections : Optional[int], default=None
            Optional minimum number of options that must be selected.

        max_selections : Optional[int], default=None
            Optional maximum number of options that can be selected.

        include_comment : bool, default=True
            Whether to include a comment field in the response.

        use_code : bool, default=False
            If True, the answer will be the indices of selected options (0-based) instead of
            the option text itself.

        question_presentation : Optional[str], default=None
            Custom template for how the question is presented to the model.

        answering_instructions : Optional[str], default=None
            Custom instructions for how the model should answer the question.

        permissive : bool, default=False
            If True, the validator will accept answers that are not in the provided options list.

        other_option_text : str, default="Other"
            The text to use for the "Other" option. This will be added to the list of options.

        Examples
        --------
        >>> q = QuestionCheckboxWithOther(
        ...     question_name="favorite_fruits",
        ...     question_text="Which fruits do you like?",
        ...     question_options=["Apple", "Banana", "Cherry", "Durian"],
        ...     min_selections=1,
        ...     max_selections=3,
        ...     other_option_text="Something else (please specify)"
        ... )
        """
        # Validate min_selections and max_selections
        if min_selections is not None and min_selections < 0:
            raise ValueError(
                f"min_selections must be non-negative, got {min_selections}"
            )
        if max_selections is not None and max_selections < 0:
            raise ValueError(
                f"max_selections must be non-negative, got {max_selections}"
            )

        # Initialize attributes
        # Note: min_selections and max_selections must be set BEFORE question_options
        # because the QuestionOptionsDescriptor validates against these values
        self.question_name = question_name
        self.question_text = question_text

        self.min_selections = min_selections
        self.max_selections = max_selections
        self.question_options = question_options
        self.other_option_text = other_option_text

        self._include_comment = include_comment
        self._use_code = use_code
        self.permissive = permissive

        self.question_presentation = question_presentation
        self.answering_instructions = answering_instructions

    def create_response_model(self):
        """
        Create a response model with the appropriate constraints.

        This method creates a Pydantic model customized with the options and
        selection count constraints specified for this question instance,
        including support for "Other: X" pattern responses.

        Returns:
            A Pydantic model class tailored to this question's constraints.

        Examples:
            >>> q = QuestionCheckboxWithOther.example()
            >>> model = q.create_response_model()
        """
        # Create options list with other_option_text added
        options = list(self.question_options)
        if self.other_option_text not in options:
            options.append(self.other_option_text)
        # Also add "Other" for backward compatibility
        if "Other" not in options:
            options.append("Other")

        if not self._use_code:
            # Use option text values as valid choices
            return create_checkbox_with_other_response_model(
                options,
                min_selections=self.min_selections,
                max_selections=self.max_selections,
                other_option_text=self.other_option_text,
                permissive=self.permissive,
            )
        else:
            # Use option indices (0, 1, 2...) as valid choices
            return create_checkbox_with_other_response_model(
                list(range(len(options))),
                min_selections=self.min_selections,
                max_selections=self.max_selections,
                other_option_text=self.other_option_text,
                permissive=self.permissive,
            )

    def _translate_answer_code_to_answer(
        self, answer_codes, scenario: "Scenario" = None
    ):
        """
        Translate the answer codes to the actual answer text.

        For checkbox questions with use_code=True, the agent responds with
        option indices (e.g., [0, 1]) which need to be translated to their
        corresponding option text values. Also handles "Other: X" patterns.

        Args:
            answer_codes: List of selected option indices or values
            scenario: Optional scenario with variables for template rendering

        Returns:
            List of selected option texts
        """
        scenario = scenario or Scenario()
        translated_options = [
            Template(str(option)).render(scenario) for option in self.question_options
        ]
        # Add other_option_text
        if self.other_option_text not in translated_options:
            translated_options.append(self.other_option_text)

        translated_codes = []
        for answer_code in answer_codes:
            if self._use_code:
                if isinstance(answer_code, int) and 0 <= answer_code < len(
                    translated_options
                ):
                    translated_codes.append(translated_options[int(answer_code)])
                else:
                    # Might be an "Other: X" pattern, keep as-is
                    translated_codes.append(answer_code)
            else:
                translated_codes.append(answer_code)
        return translated_codes

    def _simulate_answer(self, human_readable=True):
        """
        Simulate a valid answer for debugging purposes.

        This method generates a random valid answer for the checkbox with other question,
        useful for testing and demonstrations.

        Args:
            human_readable: If True, return option text values; if False, return indices

        Returns:
            A dictionary with a valid random answer
        """
        from edsl.utilities.utilities import random_string

        min_sel = self.min_selections or 1
        max_sel = self.max_selections or len(self.question_options)
        # Ensure we don't try to select more options than available
        max_sel = min(max_sel, len(self.question_options))
        min_sel = min(min_sel, max_sel)

        num_selections = random.randint(min_sel, max_sel)

        if human_readable:
            # Select a random number of options from self.question_options
            selected_options = random.sample(self.question_options, num_selections)
            # Randomly include an "Other" response
            if random.random() > 0.7:
                selected_options.append(f"{self.other_option_text}: {random_string()}")
            answer = {
                "answer": selected_options,
                "comment": random_string(),
            }
        else:
            # Select a random number of indices from the range of self.question_options
            selected_indices = random.sample(
                range(len(self.question_options)), num_selections
            )
            answer = {
                "answer": selected_indices,
                "comment": random_string(),
            }
        return answer

    @property
    def question_html_content(self) -> str:
        """
        Generate HTML content for rendering the question in web interfaces.

        This property generates HTML markup for the question when it needs to be
        displayed in web interfaces or HTML contexts. For a checkbox with other question,
        this is a set of checkbox input elements plus a text input for "Other".

        Returns:
            str: HTML markup for rendering the question.
        """
        instructions = ""
        if self.min_selections is not None:
            instructions += f"Select at least {self.min_selections} option(s). "
        if self.max_selections is not None:
            instructions += f"Select at most {self.max_selections} option(s)."

        question_html_content = Template(
            """
        <p>{{ instructions }}</p>
        {% for option in question_options %}
        <div>
        <input type="checkbox" id="{{ option }}" name="{{ question_name }}" value="{{ option }}">
        <label for="{{ option }}">{{ option }}</label>
        </div>
        {% endfor %}

        <div>
        <input type="checkbox" id="{{ other_option }}" name="{{ question_name }}" value="{{ other_option }}">
        <label for="{{ other_option }}">{{ other_option }}</label>
        <input type="text" id="{{ question_name }}_other_text" name="{{ question_name }}_other_text"
               placeholder="Please specify" style="display:none;">
        </div>

        <script>
        document.getElementById('{{ other_option }}').addEventListener('change', function() {
            document.getElementById('{{ question_name }}_other_text').style.display =
                this.checked ? 'inline-block' : 'none';
        });
        </script>
        """
        ).render(
            instructions=instructions,
            question_name=self.question_name,
            question_options=self.question_options,
            other_option=self.other_option_text,
        )
        return question_html_content

    @classmethod
    @inject_exception
    def example(
        cls, include_comment=False, use_code=False
    ) -> "QuestionCheckboxWithOther":
        """
        Create an example instance of a checkbox with other question.

        This class method creates a predefined example of a checkbox with other question
        for demonstration, testing, and documentation purposes.

        Args:
            include_comment: Whether to include a comment field with the answer.
            use_code: Whether to use indices (True) or values (False) for answer codes.

        Returns:
            QuestionCheckboxWithOther: An example checkbox with other question.

        Examples:
            >>> q = QuestionCheckboxWithOther.example()
            >>> q.question_name
            'favorite_foods'
            >>> len(q.question_options)
            5
            >>> q.min_selections
            1
            >>> q.max_selections
            3
        """
        return cls(
            question_name="favorite_foods",
            question_text="Which of the following foods do you enjoy? Select all that apply.",
            question_options=[
                "Pizza",
                "Sushi",
                "Tacos",
                "Pasta",
                "Salad",
            ],
            min_selections=1,
            max_selections=3,
            use_code=use_code,
            include_comment=include_comment,
            other_option_text="Other (please specify)",
        )


def main():
    """
    Demonstrate the functionality of the QuestionCheckboxWithOther class.

    This function creates an example checkbox with other question and demonstrates its
    key features including validation, serialization, and answer simulation.
    """
    print("Creating a QuestionCheckboxWithOther example...")
    q = QuestionCheckboxWithOther.example()
    print(f"Question text: {q.question_text}")
    print(f"Question name: {q.question_name}")
    print(f"Question options: {q.question_options}")
    print(f"Other option text: {q.other_option_text}")
    print(f"Min selections: {q.min_selections}")
    print(f"Max selections: {q.max_selections}")

    # Validate an answer
    print("\nValidating an answer...")
    valid_answer = {"answer": ["Pizza", "Sushi"], "comment": "I like these foods"}
    validated = q._validate_answer(valid_answer)
    print(f"Validated answer: {validated}")

    # Validate an answer with Other
    print("\nValidating an answer with Other...")
    other_answer = {
        "answer": ["Pizza", "Other (please specify): Ramen"],
        "comment": "Added my favorite",
    }
    validated_other = q._validate_answer(other_answer)
    print(f"Validated answer with Other: {validated_other}")

    # Simulate answers
    print("\nSimulating answers...")
    simulated = q._simulate_answer(human_readable=True)
    print(f"Simulated human-readable answer: {simulated}")

    # Serialization demonstration
    print("\nTesting serialization...")
    serialized = q.to_dict()
    print(f"Serialized question (keys): {list(serialized.keys())}")
    deserialized = QuestionBase.from_dict(serialized)
    print(
        f"Deserialization successful: {deserialized.question_text == q.question_text}"
    )


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
