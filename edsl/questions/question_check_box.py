from __future__ import annotations
from typing import Any, Optional, TYPE_CHECKING

import random
from jinja2 import Template
from pydantic import BaseModel, Field, model_validator, ValidationError
from typing import List, Literal, Annotated

from .exceptions import QuestionAnswerValidationError
from ..scenarios import Scenario

from .question_base import QuestionBase
from .descriptors import (
    IntegerDescriptor,
    QuestionOptionsDescriptor,
)
from .decorators import inject_exception
from .response_validator_abc import ResponseValidatorABC

if TYPE_CHECKING:
    pass


class CheckboxResponse(BaseModel):
    """
    Base Pydantic model for validating checkbox responses.
    
    This model defines the structure and validation rules for responses to
    checkbox questions, ensuring that selected options are properly formatted
    as a list of choices.
    
    Attributes:
        answer: List of selected choices
        comment: Optional comment provided with the answer
        generated_tokens: Optional raw LLM output for token tracking
        
    Examples:
        >>> # Valid response with list of options
        >>> response = CheckboxResponse(answer=[0, 1])
        >>> response.answer
        [0, 1]
        
        >>> # Valid response with comment
        >>> response = CheckboxResponse(answer=[1], comment="This is my choice")
        >>> response.answer
        [1]
        >>> response.comment
        'This is my choice'
        
        >>> # Invalid non-list answer
        >>> try:
        ...     CheckboxResponse(answer=1)
        ... except Exception as e:
        ...     print("Validation error occurred")
        Validation error occurred
    """
    answer: List[Any]
    comment: Optional[str] = None
    generated_tokens: Optional[Any] = None


def create_checkbox_response_model(
    choices: list,
    min_selections: Optional[int] = None,
    max_selections: Optional[int] = None,
    permissive: bool = False,
):
    """
    Dynamically create a CheckboxResponse model with a predefined list of choices.
    
    This function creates a customized Pydantic model for checkbox questions that
    validates both the format of the response and any constraints on selection count.
    
    Args:
        choices: A list of allowed values for the answer field
        min_selections: Optional minimum number of selections required
        max_selections: Optional maximum number of selections allowed
        permissive: If True, constraints are not enforced
        
    Returns:
        A new Pydantic model class with appropriate validation
        
    Examples:
        >>> # Create model with constraints
        >>> choices = [0, 1, 2, 3]
        >>> ConstrainedModel = create_checkbox_response_model(
        ...     choices=choices, 
        ...     min_selections=1, 
        ...     max_selections=2
        ... )
        
        >>> # Valid response within constraints
        >>> response = ConstrainedModel(answer=[0, 1])
        >>> response.answer
        [0, 1]
        
        >>> # Too few selections fails validation
        >>> try:
        ...     ConstrainedModel(answer=[])
        ... except Exception as e:
        ...     "at least 1" in str(e)
        True
        
        >>> # Too many selections fails validation
        >>> try:
        ...     ConstrainedModel(answer=[0, 1, 2])
        ... except Exception as e:
        ...     "at most 2" in str(e)
        True
        
        >>> # Invalid choice fails validation
        >>> try:
        ...     ConstrainedModel(answer=[4])
        ... except Exception as e:
        ...     any(x in str(e) for x in ["Invalid choice", "not a valid enumeration member", "validation error"])
        True
        
        >>> # Permissive model ignores constraints
        >>> PermissiveModel = create_checkbox_response_model(
        ...     choices=choices, 
        ...     min_selections=1, 
        ...     max_selections=2, 
        ...     permissive=True
        ... )
        >>> response = PermissiveModel(answer=[0, 1, 2])
        >>> len(response.answer)
        3
    """
    # Convert the choices list to a tuple for use with Literal
    choice_tuple = tuple(choices)

    if permissive:
        # For permissive mode, we still validate the choice values but ignore count constraints
        class PermissiveCheckboxResponse(CheckboxResponse):
            """Checkbox response model with choices validation but no count constraints."""
            
            answer: Annotated[
                List[Literal[choice_tuple]],
                Field(description="List of selected choices"),
            ]
            
            @model_validator(mode='after')
            def validate_choices(self):
                """Validate that each selected choice is valid."""
                for choice in self.answer:
                    if choice not in choices:
                        validation_error = ValidationError.from_exception_data(
                            title='CheckboxResponse',
                            line_errors=[{
                                'type': 'value_error',
                                'loc': ('answer',),
                                'msg': f'Invalid choice: {choice}. Must be one of: {choices}',
                                'input': choice,
                                'ctx': {'error': 'Invalid choice'}
                            }]
                        )
                        raise QuestionAnswerValidationError(
                            message=f"Invalid choice: {choice}. Must be one of: {choices}",
                            data=self.model_dump(),
                            model=self.__class__,
                            pydantic_error=validation_error
                        )
                return self
                
        return PermissiveCheckboxResponse
    else:
        # For non-permissive mode, enforce both choice values and count constraints
        class ConstrainedCheckboxResponse(CheckboxResponse):
            """Checkbox response model with both choice and count constraints."""
            
            answer: Annotated[
                List[Literal[choice_tuple]],
                Field(description="List of selected choices"),
            ]
            
            @model_validator(mode='after')
            def validate_selection_count(self):
                """Validate that the number of selections meets constraints."""
                if min_selections is not None and len(self.answer) < min_selections:
                    validation_error = ValidationError.from_exception_data(
                        title='CheckboxResponse',
                        line_errors=[{
                            'type': 'value_error',
                            'loc': ('answer',),
                            'msg': f'Must select at least {min_selections} option(s)',
                            'input': self.answer,
                            'ctx': {'error': 'Too few selections'}
                        }]
                    )
                    raise QuestionAnswerValidationError(
                        message=f"Must select at least {min_selections} option(s), got {len(self.answer)}",
                        data=self.model_dump(),
                        model=self.__class__,
                        pydantic_error=validation_error
                    )
                
                if max_selections is not None and len(self.answer) > max_selections:
                    validation_error = ValidationError.from_exception_data(
                        title='CheckboxResponse',
                        line_errors=[{
                            'type': 'value_error',
                            'loc': ('answer',),
                            'msg': f'Must select at most {max_selections} option(s)',
                            'input': self.answer,
                            'ctx': {'error': 'Too many selections'}
                        }]
                    )
                    raise QuestionAnswerValidationError(
                        message=f"Must select at most {max_selections} option(s), got {len(self.answer)}",
                        data=self.model_dump(),
                        model=self.__class__,
                        pydantic_error=validation_error
                    )
                
                # Also validate that each choice is valid
                for choice in self.answer:
                    if choice not in choices:
                        validation_error = ValidationError.from_exception_data(
                            title='CheckboxResponse',
                            line_errors=[{
                                'type': 'value_error',
                                'loc': ('answer',),
                                'msg': f'Invalid choice: {choice}. Must be one of: {choices}',
                                'input': choice,
                                'ctx': {'error': 'Invalid choice'}
                            }]
                        )
                        raise QuestionAnswerValidationError(
                            message=f"Invalid choice: {choice}. Must be one of: {choices}",
                            data=self.model_dump(),
                            model=self.__class__,
                            pydantic_error=validation_error
                        )
                
                return self
                
        return ConstrainedCheckboxResponse


class CheckBoxResponseValidator(ResponseValidatorABC):
    """
    Validator for checkbox question responses.
    
    This class implements the validation and fixing logic for checkbox responses.
    It ensures that responses contain valid selections from the available options
    and that the number of selections meets any constraints.
    
    Attributes:
        required_params: List of required parameters for validation.
        valid_examples: Examples of valid responses for testing.
        invalid_examples: Examples of invalid responses for testing.
        
    Examples:
        >>> from edsl import QuestionCheckBox
        >>> q = QuestionCheckBox.example()
        >>> validator = q.response_validator
        
        >>> # Fix string to list
        >>> response = {"answer": 1}
        >>> fixed = validator.fix(response)
        >>> isinstance(fixed["answer"], list)
        True
        
        >>> # Extract selections from text
        >>> response = {"generated_tokens": "I choose options 0 and 2"}
        >>> fixed = validator.fix(response)
        >>> sorted(fixed["answer"])
        [0, 2]
        
        >>> # Fix comma-separated list
        >>> response = {"generated_tokens": "0, 1, 3"}
        >>> fixed = validator.fix(response)
        >>> sorted(fixed["answer"])
        [0, 1, 3]
        
        >>> # Preserve comments when fixing
        >>> response = {"answer": 1, "comment": "My explanation"}
        >>> fixed = validator.fix(response)
        >>> "comment" in fixed and fixed["comment"] == "My explanation"
        True
    """
    required_params = [
        "question_options",
        "min_selections",
        "max_selections",
        "use_code",
        "permissive",
    ]

    valid_examples = [
        ({"answer": [1, 2]}, {"question_options": ["Good", "Great", "OK", "Bad"]})
    ]

    invalid_examples = [
        (
            {"answer": [-1]},
            {"question_options": ["Good", "Great", "OK", "Bad"]},
            "Invalid choice",
        ),
        (
            {"answer": 1},
            {"question_options": ["Good", "Great", "OK", "Bad"]},
            "value is not a valid list",
        ),
        (
            {"answer": [1, 2, 3, 4]},
            {
                "question_options": ["Good", "Great", "OK", "Bad"],
                "min_selections": 1,
                "max_selections": 2,
            },
            "Must select at most 2",
        ),
    ]

    def fix(self, response, verbose=False):
        """
        Fix common issues in checkbox responses.
        
        This method attempts to extract valid selections from responses with
        format issues. It can handle:
        1. Single values that should be lists
        2. Comma-separated strings in answer field or generated_tokens
        3. Finding option indices mentioned in text
        
        Args:
            response: The response dictionary to fix
            verbose: If True, print information about the fixing process
            
        Returns:
            A fixed version of the response dictionary with a valid list of selections
            
        Notes:
            - First tries to convert to a list if the answer is not already a list
            - Then tries to parse comma-separated values from answer or generated_tokens
            - Finally tries to find option indices mentioned in the text
            - Preserves any comment in the original response
        """
        if verbose:
            print("Invalid response of QuestionCheckBox was: ", response)
        
        # Check if answer exists and is a comma-separated string (common LLM output format)
        if "answer" in response and isinstance(response["answer"], str) and "," in response["answer"]:
            if verbose:
                print(f"Parsing comma-separated answer string: {response['answer']}")
            
            # Split by commas and strip whitespace
            proposed_list = response["answer"].split(",")
            proposed_list = [item.strip() for item in proposed_list]
            
            # Try to convert to integers if use_code is True
            if self.use_code:
                try:
                    proposed_list = [int(i) for i in proposed_list]
                except ValueError:
                    # If we can't convert to integers, try to match values to indices
                    if verbose:
                        print("Could not convert comma-separated values to integers, trying to match options")
                    
                    # Try to match option text values to their indices
                    index_map = {}
                    for i, option in enumerate(self.question_options):
                        index_map[option.lower().strip()] = i
                    
                    converted_list = []
                    for item in proposed_list:
                        item_lower = item.lower().strip()
                        if item_lower in index_map:
                            converted_list.append(index_map[item_lower])
                            
                    if converted_list:
                        proposed_list = converted_list
                    
            if verbose:
                print("Proposed solution from comma separation is: ", proposed_list)
            
            proposed_data = {
                "answer": proposed_list,
                "comment": response.get("comment"),
                "generated_tokens": response.get("generated_tokens"),
            }
            
            # Try validating with the proposed solution
            try:
                validated = self._base_validate(proposed_data)
                return validated.model_dump()
            except Exception as e:
                if verbose:
                    print(f"Comma-separated solution invalid: {e}")
            
        # If answer exists but is not a list, convert it to a list
        elif "answer" in response and not isinstance(response["answer"], list):
            if verbose:
                print(f"Converting non-list answer {response['answer']} to a list")
            answer_value = response["answer"]
            response = {**response, "answer": [answer_value]}
            
            # Try validating the fixed response
            try:
                validated = self._base_validate(response)
                return validated.model_dump()
            except Exception:
                if verbose:
                    print("Converting to list didn't fix the issue")
        
        # Try parsing from generated_tokens if present
        response_text = response.get("generated_tokens")
        if response_text and isinstance(response_text, str):
            # Try comma-separated list first
            if "," in response_text:
                proposed_list = response_text.split(",")
                proposed_list = [item.strip() for item in proposed_list]
                
                if self.use_code:
                    try:
                        proposed_list = [int(i) for i in proposed_list]
                    except ValueError:
                        # If we can't convert to integers, try to match values to indices
                        if verbose:
                            print("Could not convert comma-separated values to integers, trying to match options")
                        
                        # Try to match option text values to their indices
                        index_map = {}
                        for i, option in enumerate(self.question_options):
                            index_map[option.lower().strip()] = i
                        
                        converted_list = []
                        for item in proposed_list:
                            item_lower = item.lower().strip()
                            if item_lower in index_map:
                                converted_list.append(index_map[item_lower])
                                
                        if converted_list:
                            proposed_list = converted_list
                
                if verbose:
                    print("Proposed solution from comma separation is: ", proposed_list)
                
                proposed_data = {
                    "answer": proposed_list,
                    "comment": response.get("comment"),
                    "generated_tokens": response.get("generated_tokens"),
                }
                
                # Try validating with the proposed solution
                try:
                    validated = self._base_validate(proposed_data)
                    return validated.model_dump()
                except Exception as e:
                    if verbose:
                        print(f"Comma-separated solution invalid: {e}")
            
            # Try finding option indices mentioned in the text
            matches = []
            for index, option in enumerate(self.question_options):
                if self.use_code:
                    if str(index) in response_text:
                        matches.append(index)
                else:
                    if option in response_text:
                        matches.append(option)
                        
            if matches:
                if verbose:
                    print(f"Found options mentioned in text: {matches}")
                    
                proposed_data = {
                    "answer": matches,
                    "comment": response.get("comment"),
                    "generated_tokens": response.get("generated_tokens"),
                }
                
                # Try validating with the proposed solution
                try:
                    validated = self._base_validate(proposed_data)
                    return validated.model_dump()
                except Exception as e:
                    if verbose:
                        print(f"Text matching solution invalid: {e}")
        
        # If nothing worked, return the original response
        return response


class QuestionCheckBox(QuestionBase):
    """
    A question that prompts the agent to select multiple options from a list.
    
    QuestionCheckBox allows agents to select one or more items from a predefined
    list of options. It's useful for "select all that apply" scenarios, multi-select
    preferences, or any question where multiple valid selections are possible.
    
    Attributes:
        question_type (str): Identifier for this question type, set to "checkbox".
        purpose (str): Brief description of when to use this question type.
        question_options: List of available options to select from.
        min_selections: Optional minimum number of selections required.
        max_selections: Optional maximum number of selections allowed.
        _response_model: Initially None, set by create_response_model().
        response_validator_class: Class used to validate and fix responses.
        
    Examples:
        >>> # Basic creation works
        >>> q = QuestionCheckBox.example()
        >>> q.question_type
        'checkbox'
        
        >>> # Create preferences question with selection constraints
        >>> q = QuestionCheckBox(
        ...     question_name="favorite_fruits", 
        ...     question_text="Which fruits do you like?",
        ...     question_options=["Apple", "Banana", "Cherry", "Durian", "Elderberry"],
        ...     min_selections=1,
        ...     max_selections=3
        ... )
        >>> q.question_options
        ['Apple', 'Banana', 'Cherry', 'Durian', 'Elderberry']
        >>> q.min_selections
        1
        >>> q.max_selections
        3
    """

    question_type = "checkbox"
    purpose = "When options are known and limited"
    question_options: list[str] = QuestionOptionsDescriptor()
    min_selections = IntegerDescriptor(none_allowed=True)
    max_selections = IntegerDescriptor(none_allowed=True)

    _response_model = None
    response_validator_class = CheckBoxResponseValidator

    def __init__(
        self,
        question_name: str,
        question_text: str,
        question_options: list[str],
        min_selections: Optional[int] = None,
        max_selections: Optional[int] = None,
        include_comment: bool = True,
        use_code: bool = True,
        question_presentation: Optional[str] = None,
        answering_instructions: Optional[str] = None,
        permissive: bool = False,
    ):
        """
        Initialize a new checkbox question.
        
        Args:
            question_name: Identifier for the question, used in results and templates.
                          Must be a valid Python variable name.
            question_text: The actual text of the question to be asked.
            question_options: List of options the agent can select from.
            min_selections: Optional minimum number of options that must be selected.
            max_selections: Optional maximum number of options that can be selected.
            include_comment: Whether to allow comments with the answer.
            use_code: If True, use indices (0,1,2...) instead of option text values.
            question_presentation: Optional custom presentation template.
            answering_instructions: Optional additional instructions.
            permissive: If True, ignore selection count constraints during validation.
            
        Examples:
            >>> q = QuestionCheckBox(
            ...     question_name="symptoms",
            ...     question_text="Select all symptoms you are experiencing:",
            ...     question_options=["Fever", "Cough", "Headache", "Fatigue"],
            ...     min_selections=1
            ... )
            >>> q.question_name
            'symptoms'
            
            >>> # Question with both min and max
            >>> q = QuestionCheckBox(
            ...     question_name="pizza_toppings",
            ...     question_text="Choose 2-4 toppings for your pizza:",
            ...     question_options=["Cheese", "Pepperoni", "Mushroom", "Onion", 
            ...                       "Sausage", "Bacon", "Pineapple"],
            ...     min_selections=2,
            ...     max_selections=4
            ... )
        """
        self.question_name = question_name
        self.question_text = question_text
        self.min_selections = min_selections
        self.max_selections = max_selections
        self.question_options = question_options

        self._include_comment = include_comment
        self._use_code = use_code
        self.permissive = permissive

        self.question_presentation = question_presentation
        self.answering_instructions = answering_instructions

    def create_response_model(self):
        """
        Create a response model with the appropriate constraints.
        
        This method creates a Pydantic model customized with the options and
        selection count constraints specified for this question instance.
        
        Returns:
            A Pydantic model class tailored to this question's constraints.
            
        Examples:
            >>> q = QuestionCheckBox.example()
            >>> model = q.create_response_model()
            >>> model(answer=[0, 2])  # Select first and third options
            ConstrainedCheckboxResponse(answer=[0, 2], comment=None, generated_tokens=None)
        """
        if not self._use_code:
            # Use option text values as valid choices
            return create_checkbox_response_model(
                self.question_options,
                min_selections=self.min_selections,
                max_selections=self.max_selections,
                permissive=self.permissive,
            )
        else:
            # Use option indices (0, 1, 2...) as valid choices
            return create_checkbox_response_model(
                list(range(len(self.question_options))),
                min_selections=self.min_selections,
                max_selections=self.max_selections,
                permissive=self.permissive,
            )

    def _translate_answer_code_to_answer(
        self, answer_codes, scenario: "Scenario" = None
    ):
        """
        Translate the answer codes to the actual answer text.
        
        For checkbox questions with use_code=True, the agent responds with
        option indices (e.g., [0, 1]) which need to be translated to their
        corresponding option text values (e.g., ["Option A", "Option B"]).
        
        Args:
            answer_codes: List of selected option indices or values
            scenario: Optional scenario with variables for template rendering
            
        Returns:
            List of selected option texts
            
        Examples:
            >>> q = QuestionCheckBox(
            ...     question_name="example",
            ...     question_text="Select options:",
            ...     question_options=["A", "B", "C"]
            ... )
            >>> q._translate_answer_code_to_answer([0, 2])
            ['A', 'C']
        """
        scenario = scenario or Scenario()
        translated_options = [
            Template(str(option)).render(scenario) for option in self.question_options
        ]
        translated_codes = []
        for answer_code in answer_codes:
            if self._use_code:
                translated_codes.append(translated_options[int(answer_code)])
            else:
                translated_codes.append(answer_code)
        return translated_codes

    def _simulate_answer(self, human_readable=True):
        """
        Simulate a valid answer for debugging purposes.
        
        This method generates a random valid answer for the checkbox question,
        useful for testing and demonstrations.
        
        Args:
            human_readable: If True, return option text values; if False, return indices
            
        Returns:
            A dictionary with a valid random answer
            
        Examples:
            >>> q = QuestionCheckBox.example()
            >>> answer = q._simulate_answer(human_readable=False)
            >>> len(answer["answer"]) >= q.min_selections
            True
            >>> len(answer["answer"]) <= q.max_selections
            True
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
        displayed in web interfaces or HTML contexts. For a checkbox question,
        this is a set of checkbox input elements, one for each option.
        
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
        """
        ).render(
            instructions=instructions,
            question_name=self.question_name,
            question_options=self.question_options,
        )
        return question_html_content

    ################
    # Helpful methods
    ################
    @classmethod
    @inject_exception
    def example(cls, include_comment=False, use_code=True) -> QuestionCheckBox:
        """
        Create an example instance of a checkbox question.
        
        This class method creates a predefined example of a checkbox question
        for demonstration, testing, and documentation purposes.
        
        Args:
            include_comment: Whether to include a comment field with the answer.
            use_code: Whether to use indices (True) or values (False) for answer codes.
                     
        Returns:
            QuestionCheckBox: An example checkbox question.
            
        Examples:
            >>> q = QuestionCheckBox.example()
            >>> q.question_name
            'never_eat'
            >>> len(q.question_options)
            5
            >>> q.min_selections
            2
            >>> q.max_selections
            5
        """
        return cls(
            question_name="never_eat",
            question_text="Which of the following foods would you eat if you had to?",
            question_options=[
                "soggy meatpie",
                "rare snails",
                "mouldy bread",
                "panda milk custard",
                "McDonalds",
            ],
            min_selections=2,
            max_selections=5,
            use_code=use_code,
            include_comment=include_comment,
        )


def main():
    """
    Demonstrate the functionality of the QuestionCheckBox class.
    
    This function creates an example checkbox question and demonstrates its
    key features including validation, serialization, and answer simulation.
    It's primarily intended for testing and development purposes.
    
    Note:
        This function will be executed when the module is run directly,
        but not when imported.
    """
    print("Creating a QuestionCheckBox example...")
    q = QuestionCheckBox.example()
    print(f"Question text: {q.question_text}")
    print(f"Question name: {q.question_name}")
    print(f"Question options: {q.question_options}")
    print(f"Min selections: {q.min_selections}")
    print(f"Max selections: {q.max_selections}")
    
    # Validate an answer
    print("\nValidating an answer...")
    valid_answer = {"answer": [1, 2], "comment": "I like these foods"}
    validated = q._validate_answer(valid_answer)
    print(f"Validated answer: {validated}")
    
    # Translate answer codes
    print("\nTranslating answer codes...")
    translated = q._translate_answer_code_to_answer([1, 2])
    print(f"Translated answer: {translated}")
    
    # Simulate answers
    print("\nSimulating answers...")
    simulated_human = q._simulate_answer(human_readable=True)
    print(f"Simulated human-readable answer: {simulated_human}")
    
    simulated_codes = q._simulate_answer(human_readable=False)
    print(f"Simulated code answer: {simulated_codes}")
    
    # Validate simulated answer
    validated_simulated = q._validate_answer(simulated_codes)
    print(f"Validated simulated answer: {validated_simulated}")
    
    # Serialization demonstration
    print("\nTesting serialization...")
    serialized = q.to_dict()
    print(f"Serialized question (keys): {list(serialized.keys())}")
    deserialized = QuestionBase.from_dict(serialized)
    print(f"Deserialization successful: {deserialized.question_text == q.question_text}")
    
    # Run doctests
    print("\nRunning doctests...")
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)
    print("Doctests completed")


if __name__ == "__main__":
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)
    
    # Uncomment to run demonstration
    # main()
