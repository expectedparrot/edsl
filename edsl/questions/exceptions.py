import json
from typing import Any
from pydantic import ValidationError

from ..base import BaseException


class QuestionErrors(BaseException):
    """
    Base exception class for question-related errors.

    This is the parent class for all exceptions related to question creation,
    validation, processing, and answer handling. It provides a consistent
    interface for error handling across the questions module.

    Attributes:
        message (str): A human-readable error message explaining the issue
    """

    def __init__(self, message="An error occurred with the question"):
        self.message = message
        super().__init__(self.message)


class QuestionAnswerValidationError(QuestionErrors):
    """
    Exception raised when an answer fails validation.

    This exception occurs when the response from a language model does not
    conform to the expected format or constraints for a specific question type.

    Common reasons for this exception:
    - Multiple choice: Answer not one of the provided options
    - Numerical: Answer not a valid number or outside allowed range
    - Checkbox: Answer not a valid list of selected options
    - Ranking: Answer does not include all items or has duplicates

    To fix this error:
    1. Check the model's response format against the question's requirements
    2. Verify that the question's instructions are clear for the language model
    3. Consider using a more capable model if consistent validation failures occur
    4. Examine the full error details which include the invalid response and validation rules

    Attributes:
        message (str): The error message
        pydantic_error (ValidationError): Underlying pydantic validation error
        data (dict): The data that failed validation
        model: The pydantic model used for validation
    """

    documentation = (
        "https://docs.expectedparrot.com/en/latest/questions.html#validation"
    )

    explanation = """
    This error occurs when the answer from the Language Model doesn't match the expected format
    or constraints for the question type. For example:
    
    • Multiple choice questions require answers from the provided options
    • Numerical questions need valid numbers within any specified range
    • Checkbox questions require a subset of valid options
    • Matrix questions need responses for each row following column constraints
    
    The error details show both what the model returned and the validation rules that were violated.
    """

    def __init__(
        self,
        message: str,
        data: dict,
        model: Any,  # for now
        pydantic_error: ValidationError,
    ):
        self.message = message
        self.pydantic_error = pydantic_error
        self.data = data
        self.model = model
        super().__init__(self.message)

        # Log validation failure for analysis
        try:
            from .validation_logger import log_validation_failure

            # Get question type and name if available
            question_type = getattr(model, "question_type", "unknown")
            question_name = getattr(model, "question_name", "unknown")

            # Log the validation failure
            log_validation_failure(
                question_type=question_type,
                question_name=question_name,
                error_message=str(message),
                invalid_data=data,
                model_schema=model.model_json_schema(),
                question_dict=getattr(model, "to_dict", lambda: None)(),
            )
        except Exception:
            # Silently ignore logging errors to not disrupt normal operation
            pass

    def __str__(self):
        if isinstance(self.message, ValidationError):
            # If it's a ValidationError, just return the core error message
            return str(self.message)
        elif hasattr(self.message, "errors"):
            # Handle the case where it's already been converted to a string but has errors
            error_list = self.message.errors()
            if error_list:
                return str(error_list[0].get("msg", "Unknown error"))
        return str(self.message)

    def to_html_dict(self):
        """
        Convert the exception to an HTML-friendly dictionary for rendering.

        This method is used for creating detailed error reports in HTML format,
        particularly in notebook environments.

        Returns:
            dict: HTML-formatted error information
        """
        # breakpoint()
        return {
            "Exception type": ("p", "/p", self.__class__.__name__),
            "Explanation": ("p", "/p", self.explanation),
            "EDSL response": (
                "pre",
                "/pre",
                json.dumps(self.data, indent=2),
            ),
            "Validating model": (
                "pre",
                "/pre",
                json.dumps(self.model.model_json_schema(), indent=2),
            ),
            "Error message": (
                "p",
                "/p",
                self.message,
            ),
            "Documentation": (
                f"a href='{self.documentation}'",
                "/a",
                self.documentation,
            ),
        }


class QuestionCreationValidationError(QuestionErrors):
    """
    Exception raised when question creation parameters are invalid.

    This exception occurs when attempting to create a question with invalid
    parameters, such as:
    - Missing required attributes
    - Invalid option formats
    - Incompatible parameter combinations

    To fix this error:
    1. Check the documentation for the specific question type
    2. Verify all required parameters are provided
    3. Ensure parameter formats match the question type's expectations
    4. Confirm that parameter combinations are compatible

    Examples:
        ```python
        # Missing required options for multiple choice
        MultipleChoice(question_text="Choose one:", options=[])  # Raises QuestionCreationValidationError

        # Invalid parameter combination
        Numerical(question_text="Enter a value:", min_value=10, max_value=5)  # Raises QuestionCreationValidationError
        ```
    """

    def __init__(self, message="Invalid parameters for question creation"):
        super().__init__(message)


class QuestionInitializationError(QuestionErrors):
    """
    Exception raised when question initialization fails due to parameter issues.

    This exception occurs when attempting to create a question with initialization
    problems, such as:
    - Misspelled parameter names (e.g., 'pydnatic_model' instead of 'pydantic_model')
    - Unknown keyword arguments
    - Required parameters missing
    - Incorrect parameter types

    To fix this error:
    1. Check the spelling of all parameter names
    2. Verify all required parameters are provided
    3. Review the question type's documentation for valid parameters
    4. Ensure parameter types match expectations

    Examples:
        ```python
        # Misspelled parameter name
        QuestionPydantic(question_name="test", question_text="Test", pydnatic_model=Model)  # Raises QuestionInitializationError

        # Unknown parameter
        QuestionMultipleChoice(question_name="test", question_text="Test", invalid_param="value")  # Raises QuestionInitializationError
        ```
    """

    documentation = (
        "https://docs.expectedparrot.com/en/latest/questions.html#initialization"
    )

    def __init__(
        self,
        message: str,
        question_type: str = None,
        invalid_parameter: str = None,
        valid_parameters: list = None,
        suggested_fix: str = None,
        **kwargs,
    ):
        self.question_type = question_type
        self.invalid_parameter = invalid_parameter
        self.valid_parameters = valid_parameters or []
        self.suggested_fix = suggested_fix

        # Build comprehensive error message
        formatted_msg = message

        if invalid_parameter and valid_parameters:
            # Try to suggest the closest matching parameter
            closest_match = self._find_closest_parameter(
                invalid_parameter, valid_parameters
            )
            if closest_match and closest_match != invalid_parameter:
                formatted_msg += f"\n\nDid you mean '{closest_match}'?"

        if invalid_parameter:
            formatted_msg += f"\n\nInvalid parameter: '{invalid_parameter}'"

        if valid_parameters:
            formatted_msg += f"\nValid parameters for {question_type or 'this question type'}: {', '.join(sorted(valid_parameters))}"

        if suggested_fix:
            formatted_msg += f"\n\nSuggested fix: {suggested_fix}"

        super().__init__(formatted_msg, **kwargs)

    def _find_closest_parameter(self, invalid_param: str, valid_params: list) -> str:
        """Find the closest matching parameter name using simple string similarity."""
        if not invalid_param or not valid_params:
            return None

        # Simple similarity check - count common characters and length difference
        def similarity_score(a: str, b: str) -> float:
            if not a or not b:
                return 0.0

            # Common characters
            common = set(a.lower()) & set(b.lower())
            common_score = len(common) / max(len(set(a.lower())), len(set(b.lower())))

            # Length similarity
            length_score = 1.0 - abs(len(a) - len(b)) / max(len(a), len(b))

            # Substring check
            substring_score = (
                0.5 if a.lower() in b.lower() or b.lower() in a.lower() else 0.0
            )

            return (common_score * 0.5) + (length_score * 0.3) + (substring_score * 0.2)

        best_match = None
        best_score = 0.0

        for param in valid_params:
            score = similarity_score(invalid_param, param)
            if score > best_score and score > 0.3:  # Only suggest if reasonably similar
                best_score = score
                best_match = param

        return best_match


class QuestionResponseValidationError(QuestionErrors):
    """
    Exception raised when a response fails structural validation.

    This exception is similar to QuestionAnswerValidationError but focuses on
    structural validation before content validation. It catches errors in the
    response structure itself.

    To fix this error:
    1. Check if the model's response format is correctly structured
    2. Verify that the response contains all required fields
    3. Ensure the response data types match expectations

    Note: This exception is primarily used in tests and internal validation.
    In most cases, QuestionAnswerValidationError provides more detailed information.
    """

    def __init__(self, message="The response structure is invalid"):
        super().__init__(message)


class QuestionAttributeMissing(QuestionErrors):
    """
    Exception raised when a required question attribute is missing.

    This exception occurs when attempting to use a question that is missing
    essential attributes needed for its operation.

    To fix this error:
    1. Check that the question has been properly initialized
    2. Verify all required attributes are set
    3. Ensure any parent class initialization is called correctly

    Note: While defined in the codebase, this exception is not actively raised
    and may be used for future validation enhancements.
    """

    def __init__(self, message="A required question attribute is missing"):
        super().__init__(message)


class QuestionSerializationError(QuestionErrors):
    """
    Exception raised when question serialization or deserialization fails.

    This exception occurs when:
    - A question cannot be properly converted to JSON format
    - A serialized question cannot be reconstructed from its JSON representation
    - Required fields are missing in the serialized data

    To fix this error:
    1. Ensure the question and all its attributes are serializable
    2. When deserializing, verify the data format matches what's expected
    3. Check for version compatibility if deserializing from an older version

    Examples:
        ```python
        question.to_dict()  # Raises QuestionSerializationError if contains unserializable attributes
        ```
    """

    def __init__(self, message="Failed to serialize or deserialize question"):
        super().__init__(message)


class QuestionScenarioRenderError(QuestionErrors):
    """
    Exception raised when a scenario cannot be rendered for a question.

    This exception occurs when:
    - The scenario template has syntax errors
    - Required variables for the template are missing
    - The rendered scenario exceeds size limits

    To fix this error:
    1. Check the scenario template syntax
    2. Ensure all required variables are provided to the template
    3. Verify that the scenario size is within acceptable limits

    Examples:
        ```python
        question.with_scenario(scenario_with_invalid_template)  # Raises QuestionScenarioRenderError
        ```
    """

    def __init__(self, message="Failed to render scenario for question"):
        super().__init__(message)


class QuestionMissingTypeError(QuestionErrors):
    """
    Exception raised when a question class is missing a required type attribute.

    This exception occurs during question registration when a question class
    doesn't define the required question_type attribute. All question classes
    must have this attribute for proper registration and identification.

    To fix this error:
    1. Add the question_type class attribute to the question class
    2. Ensure the question_type is a unique identifier for the question type

    Examples:
        ```python
        class MyQuestion(Question):  # Missing question_type attribute
            pass
        # Registration would raise QuestionMissingTypeError
        ```
    """

    def __init__(self, message="Question class is missing required type attribute"):
        super().__init__(message)


class QuestionBadTypeError(QuestionErrors):
    """
    Exception raised when a question class has an invalid __init__ method signature.

    This exception occurs during question registration when a question class
    doesn't have the required parameters in its __init__ method. All question
    classes must follow a standard parameter pattern for consistency.

    To fix this error:
    1. Ensure the question class __init__ method includes the necessary parameters
    2. Match the parameter pattern required by the question registry

    Examples:
        ```python
        class MyQuestion(Question):
            question_type = "my_question"
            def __init__(self, missing_required_params):  # Invalid signature
                pass
        # Registration would raise QuestionBadTypeError
        ```
    """

    def __init__(self, message="Question class has invalid __init__ method signature"):
        super().__init__(message)


class QuestionTypeError(QuestionErrors):
    """
    Exception raised when a TypeError occurs in the questions module.

    This exception wraps standard Python TypeErrors to provide a consistent
    exception handling approach within the EDSL framework. It's used when
    a type-related error occurs during question operations.

    Examples:
        - Attempting to access or operate on a question attribute with the wrong type
        - Passing incorrect types to question methods
        - Type conversion failures during question processing
    """

    def __init__(self, message="A type error occurred while processing the question"):
        super().__init__(message)


class QuestionValueError(QuestionErrors):
    """
    Exception raised when a ValueError occurs in the questions module.

    This exception wraps standard Python ValueErrors to provide a consistent
    exception handling approach within the EDSL framework. It's used when
    a value-related error occurs during question operations.

    Examples:
        - Invalid values for question parameters
        - Out-of-range values for numerical questions
        - Invalid option selections for multiple choice questions
    """

    def __init__(self, message="An invalid value was provided for the question"):
        super().__init__(message)


class QuestionKeyError(QuestionErrors):
    """
    Exception raised when a KeyError occurs in the questions module.

    This exception wraps standard Python KeyErrors to provide a consistent
    exception handling approach within the EDSL framework. It's used when
    a key-related error occurs during question operations.

    Examples:
        - Attempting to access a non-existent attribute via dictionary-style access
        - Missing keys in question option dictionaries
        - Key errors during question serialization or deserialization
    """

    def __init__(self, message="A key error occurred while processing the question"):
        super().__init__(message)


class QuestionNotImplementedError(QuestionErrors):
    """
    Exception raised when a method that should be implemented is not.

    This exception wraps standard Python NotImplementedError to provide a consistent
    exception handling approach within the EDSL framework. It's used when
    a required method is called but not implemented.

    Examples:
        - Abstract methods that must be overridden in subclasses
        - Placeholder methods that should be implemented in concrete classes
        - Methods that are required by an interface but not yet implemented
    """

    def __init__(self, message="This method must be implemented in a subclass"):
        super().__init__(message)
