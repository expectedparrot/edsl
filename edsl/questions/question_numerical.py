from __future__ import annotations

from typing import Any, Optional, Union
import re
from pydantic import BaseModel, model_validator, ValidationError

from .question_base import QuestionBase
from .descriptors import NumericalOrNoneDescriptor
from .decorators import inject_exception
from .response_validator_abc import ResponseValidatorABC
from .exceptions import QuestionAnswerValidationError


class NumericalResponse(BaseModel):
    """
    Pydantic model for validating numerical responses.
    
    This model defines the structure and validation rules for responses to
    numerical questions. It ensures that responses contain a valid number
    and that the number falls within any specified range constraints.
    
    Attributes:
        answer: The numerical response (int or float)
        comment: Optional comment provided with the answer
        generated_tokens: Optional raw LLM output for token tracking
        
    Examples:
        >>> # Valid response with just answer
        >>> response = NumericalResponse(answer=42)
        >>> response.answer
        42
        
        >>> # Valid response with comment
        >>> response = NumericalResponse(answer=3.14, comment="Pi approximation")
        >>> response.answer
        3.14
        >>> response.comment
        'Pi approximation'
        
        >>> # Invalid non-numeric answer
        >>> try:
        ...     NumericalResponse(answer="not a number")
        ... except Exception as e:
        ...     print("Validation error occurred")
        Validation error occurred
    """
    answer: Union[int, float]
    comment: Optional[str] = None
    generated_tokens: Optional[Any] = None


def create_numeric_response(
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    permissive=False,
):
    """Create a constrained numerical response model with range validation.
    
    Examples:
        >>> # Create model with constraints
        >>> ConstrainedModel = create_numeric_response(min_value=0, max_value=100)
        >>> response = ConstrainedModel(answer=42)
        >>> response.answer
        42
        
        >>> # Test min value constraint failure
        >>> try:
        ...     ConstrainedModel(answer=-5)
        ... except Exception as e:
        ...     "must be greater than or equal to" in str(e)
        True
        
        >>> # Test max value constraint failure
        >>> try:
        ...     ConstrainedModel(answer=150)
        ... except Exception as e:
        ...     "must be less than or equal to" in str(e)
        True
        
        >>> # Permissive mode ignores constraints
        >>> PermissiveModel = create_numeric_response(min_value=0, max_value=100, permissive=True)
        >>> response = PermissiveModel(answer=150)
        >>> response.answer
        150
    """
    if permissive:
        return NumericalResponse
    
    class ConstrainedNumericResponse(NumericalResponse):
        """Numerical response model with added range constraints."""
        
        @model_validator(mode='after')
        def validate_range_constraints(self):
            """Validate that the number meets range constraints."""
            if min_value is not None and self.answer < min_value:
                validation_error = ValidationError.from_exception_data(
                    title='ConstrainedNumericResponse',
                    line_errors=[{
                        'type': 'value_error',
                        'loc': ('answer',),
                        'msg': f'Answer must be greater than or equal to {min_value}',
                        'input': self.answer,
                        'ctx': {'error': 'Value too small'}
                    }]
                )
                raise QuestionAnswerValidationError(
                    message=f"Answer {self.answer} must be greater than or equal to {min_value}",
                    data=self.model_dump(),
                    model=self.__class__,
                    pydantic_error=validation_error
                )
                
            if max_value is not None and self.answer > max_value:
                validation_error = ValidationError.from_exception_data(
                    title='ConstrainedNumericResponse',
                    line_errors=[{
                        'type': 'value_error',
                        'loc': ('answer',),
                        'msg': f'Answer must be less than or equal to {max_value}',
                        'input': self.answer,
                        'ctx': {'error': 'Value too large'}
                    }]
                )
                raise QuestionAnswerValidationError(
                    message=f"Answer {self.answer} must be less than or equal to {max_value}",
                    data=self.model_dump(),
                    model=self.__class__,
                    pydantic_error=validation_error
                )
            return self
    
    return ConstrainedNumericResponse


class NumericalResponseValidator(ResponseValidatorABC):
    """
    Validator for numerical question responses.
    
    This class implements the validation and fixing logic for numerical responses.
    It ensures that responses contain valid numbers within specified ranges and
    provides methods to fix common issues in responses.
    
    Attributes:
        required_params: List of required parameters for validation.
        valid_examples: Examples of valid responses for testing.
        invalid_examples: Examples of invalid responses for testing.
        
    Examples:
        >>> from edsl import QuestionNumerical
        >>> q = QuestionNumerical.example()
        >>> validator = q.response_validator
        
        >>> # Fix string to number
        >>> response = {"answer": "42"}
        >>> fixed = validator.fix(response)
        >>> fixed
        {'answer': '42'}
        
        >>> # Extract number from text
        >>> response = {"answer": "The answer is 42"}
        >>> fixed = validator.fix(response)
        >>> fixed
        {'answer': '42'}
        
        >>> # Preserve comments when fixing
        >>> response = {"answer": "The answer is 42", "comment": "My explanation"}
        >>> fixed = validator.fix(response)
        >>> fixed
        {'answer': '42', 'comment': 'My explanation'}
    """
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
        """
        Fix common issues in numerical responses.
        
        This method attempts to extract valid numbers from text responses,
        handle formatting issues, and ensure the response contains a valid number.
        
        Args:
            response: The response dictionary to fix.
            verbose: If True, print information about the fixing process.
            
        Returns:
            A fixed version of the response dictionary.
            
        Notes:
            - Attempts to extract numbers using regex pattern matching
            - Removes commas from numbers (e.g., "1,000" → "1000")
            - Preserves any comment in the original response
        """
        response_text = str(response).lower()

        if verbose:
            print(f"Invalid generated tokens was: {response_text}")
            
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
        """Method preserved for compatibility, constraints handled in Pydantic model."""
        pass


class QuestionNumerical(QuestionBase):
    """
    A question that prompts the agent to answer with a numerical value.
    
    QuestionNumerical is designed for responses that must be numbers, with optional
    range constraints to ensure values fall within acceptable bounds. It's useful for
    age questions, ratings, measurements, and any scenario requiring numerical answers.
    
    Attributes:
        question_type (str): Identifier for this question type, set to "numerical".
        min_value: Optional lower bound for acceptable answers.
        max_value: Optional upper bound for acceptable answers.
        _response_model: Initially None, set by create_response_model().
        response_validator_class: Class used to validate and fix responses.
        
    Examples:
        >>> # Basic self-check passes
        >>> QuestionNumerical.self_check()
        
        >>> # Create age question with range constraints
        >>> q = QuestionNumerical(
        ...     question_name="age", 
        ...     question_text="How old are you in years?",
        ...     min_value=0,
        ...     max_value=120
        ... )
        >>> q.min_value
        0
        >>> q.max_value
        120
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
        """
        Initialize a new numerical question.
        
        Args:
            question_name: Identifier for the question, used in results and templates.
                          Must be a valid Python variable name.
            question_text: The actual text of the question to be asked.
            min_value: Optional minimum value for the answer (inclusive).
            max_value: Optional maximum value for the answer (inclusive).
            include_comment: Whether to allow comments with the answer.
            question_presentation: Optional custom presentation template.
            answering_instructions: Optional additional instructions.
            permissive: If True, ignore min/max constraints during validation.
            
        Examples:
            >>> q = QuestionNumerical(
            ...     question_name="temperature",
            ...     question_text="What is the temperature in Celsius?",
            ...     min_value=-273.15  # Absolute zero
            ... )
            >>> q.question_name
            'temperature'
            
            >>> # Question with both min and max
            >>> q = QuestionNumerical(
            ...     question_name="rating",
            ...     question_text="Rate from 1 to 10",
            ...     min_value=1,
            ...     max_value=10
            ... )
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
        """
        Create a response model with the appropriate constraints.
        
        This method creates a Pydantic model customized with the min/max constraints
        specified for this question instance. If permissive=True, constraints are ignored.
        
        Returns:
            A Pydantic model class tailored to this question's constraints.
            
        Examples:
            >>> q = QuestionNumerical.example()
            >>> model = q.create_response_model()
            >>> model(answer=45).answer
            45
        """
        return create_numeric_response(self.min_value, self.max_value, self.permissive)
        
    def _simulate_answer(self, human_readable: bool = False) -> dict:
        """
        Generate a simulated valid answer respecting min/max constraints.
        
        Overrides the base class method to ensure values are within defined bounds.
        
        Args:
            human_readable: Flag for human-readable output (not used for numerical questions)
            
        Returns:
            A dictionary with a valid numerical answer within constraints
            
        Examples:
            >>> q = QuestionNumerical(question_name="test", question_text="Test", min_value=1, max_value=10)
            >>> answer = q._simulate_answer()
            >>> 1 <= answer["answer"] <= 10
            True
        """
        from random import randint, uniform
        
        min_val = self.min_value if self.min_value is not None else 0
        max_val = self.max_value if self.max_value is not None else 100
        
        # Generate a value within the constraints
        if isinstance(min_val, int) and isinstance(max_val, int):
            value = randint(int(min_val), int(max_val))
        else:
            value = uniform(float(min_val), float(max_val))
            
        return {"answer": value, "comment": None, "generated_tokens": None}

    ################
    # Answer methods
    ################

    @property
    def question_html_content(self) -> str:
        """
        Generate HTML content for rendering the question in web interfaces.
        
        This property generates HTML markup for the question when it needs to be
        displayed in web interfaces or HTML contexts. For a numerical question,
        this is typically an input element with type="number".
        
        Returns:
            str: HTML markup for rendering the question.
        """
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
        """
        Create an example instance of a numerical question.
        
        This class method creates a predefined example of a numerical question
        for demonstration, testing, and documentation purposes.
        
        Args:
            include_comment: Whether to include a comment field with the answer.
                           
        Returns:
            QuestionNumerical: An example numerical question.
            
        Examples:
            >>> q = QuestionNumerical.example()
            >>> q.question_name
            'age'
            >>> q.question_text
            'You are a 45 year old man. How old are you in years?'
            >>> q.min_value
            0
            >>> q.max_value
            86.7
        """
        return cls(
            question_name="age",
            question_text="You are a 45 year old man. How old are you in years?",
            min_value=0,
            max_value=86.7,
            include_comment=include_comment,
        )


def main():
    """
    Demonstrate the functionality of the QuestionNumerical class.
    
    This function creates an example numerical question and demonstrates its
    key features including validation, serialization, and answer simulation.
    It's primarily intended for testing and development purposes.
    
    Note:
        This function will be executed when the module is run directly,
        but not when imported.
    """
    # Create an example question
    q = QuestionNumerical.example()
    print(f"Question text: {q.question_text}")
    print(f"Question name: {q.question_name}")
    print(f"Min value: {q.min_value}")
    print(f"Max value: {q.max_value}")
    
    # Validate an answer
    valid_answer = {"answer": 42}
    validated = q._validate_answer(valid_answer)
    print(f"Validated answer: {validated}")
    
    # Test constraints - this should be in range
    valid_constrained = {"answer": 75}
    constrained = q._validate_answer(valid_constrained)
    print(f"Valid constrained answer: {constrained}")
    
    # Simulate an answer
    simulated = q._simulate_answer()
    print(f"Simulated answer: {simulated}")
    
    # Serialization demonstration
    serialized = q.to_dict()
    print(f"Serialized: {serialized}")
    deserialized = QuestionBase.from_dict(serialized)
    print(f"Deserialization successful: {deserialized.question_text == q.question_text}")
    
    # Run doctests
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)
    print("Doctests completed")


if __name__ == "__main__":
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)
    
    # Uncomment to run demonstration
    # main()
