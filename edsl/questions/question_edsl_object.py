from __future__ import annotations
from typing import Optional, Any, Dict
from uuid import uuid4
import json

from pydantic import BaseModel, field_validator

from .question_base import QuestionBase
from .response_validator_abc import ResponseValidatorABC
from .decorators import inject_exception
from .register_questions_meta import RegisterQuestionsMeta
from ..base import RegisterSubclassesMeta


class EDSLObjectResponse(BaseModel):
    """
    Pydantic model for validating EDSL object responses.

    This model defines the structure and validation rules for responses to
    EDSL object questions. It ensures that responses contain a valid dictionary
    representation of an EDSL object that can be instantiated.

    Attributes:
        answer: The dictionary representation of an EDSL object.
        generated_tokens: Optional raw LLM output for token tracking.

    Examples:
        >>> # Valid response with Question object dict
        >>> response = EDSLObjectResponse(answer={"question_type": "free_text", "question_name": "test", "question_text": "Test?"})
        >>> response.answer["question_type"]
        'free_text'
    """

    answer: Dict[str, Any]
    generated_tokens: Optional[str] = None

    @field_validator("answer")
    @classmethod
    def validate_answer_is_dict(cls, v):
        """
        Validate that the answer is a dictionary.

        Args:
            v: The value to validate.

        Returns:
            The validated dictionary.

        Raises:
            ValueError: If the answer is not a dictionary.
        """
        if not isinstance(v, dict):
            raise ValueError("Answer must be a dictionary")
        return v


class EDSLObjectResponseValidator(ResponseValidatorABC):
    """
    Validator for EDSL object question responses.

    This class implements the validation and fixing logic for EDSL object responses.
    It ensures that responses contain a valid dictionary that can be used to
    instantiate the expected EDSL object type.

    Attributes:
        required_params: List of required parameters for validation.
        valid_examples: Examples of valid responses for testing.
        invalid_examples: Examples of invalid responses for testing.
    """

    required_params = ["expected_object_type"]
    valid_examples = [
        (
            {
                "answer": {
                    "question_type": "free_text",
                    "question_name": "test",
                    "question_text": "Test?",
                }
            },
            {"expected_object_type": "free_text"},
        )
    ]
    invalid_examples = [
        (
            {"answer": "not a dict"},
            {"expected_object_type": "free_text"},
            "Answer must be a dictionary representing an EDSL object.",
        ),
        (
            {"answer": {"invalid": "object"}},
            {"expected_object_type": "free_text"},
            "Answer dictionary cannot be instantiated as expected EDSL object type.",
        ),
    ]

    def fix(self, response: dict, verbose: bool = False) -> dict:
        """
        Fix common issues in EDSL object responses.

        This method attempts to fix invalid responses by parsing JSON strings
        and ensuring the answer field contains a valid dictionary.

        Args:
            response: The response dictionary to fix.
            verbose: If True, print information about the fixing process.

        Returns:
            A fixed version of the response dictionary.
        """
        answer = response.get("answer")
        generated_tokens = response.get("generated_tokens")

        # Try to parse answer as JSON if it's a string
        if isinstance(answer, str):
            try:
                answer = json.loads(answer)
                if verbose:
                    print(f"Parsed answer from JSON string: {answer}")
            except json.JSONDecodeError:
                if verbose:
                    print(f"Could not parse answer as JSON: {answer}")
                pass

        # Try to parse generated_tokens as JSON if answer parsing failed
        if not isinstance(answer, dict) and isinstance(generated_tokens, str):
            try:
                answer = json.loads(generated_tokens)
                if verbose:
                    print(f"Parsed answer from generated_tokens JSON: {answer}")
            except json.JSONDecodeError:
                if verbose:
                    print(
                        f"Could not parse generated_tokens as JSON: {generated_tokens}"
                    )
                pass

        # If still not a dict, create empty dict
        if not isinstance(answer, dict):
            answer = {}
            if verbose:
                print("Created empty dict as fallback answer")

        return {"answer": answer, "generated_tokens": generated_tokens}

    def validate_object_instantiation(
        self, answer_dict: dict, expected_object_type: str
    ) -> bool:
        """
        Validate that the answer dictionary can be used to instantiate the expected EDSL object.

        Args:
            answer_dict: Dictionary representation of the EDSL object.
            expected_object_type: Name of the expected EDSL object class.

        Returns:
            bool: True if the object can be instantiated, False otherwise.
        """
        try:
            # For questions, use the question registry
            if (
                expected_object_type
                in RegisterQuestionsMeta.question_types_to_classes()
            ):
                question_registry = RegisterQuestionsMeta.question_types_to_classes()
                object_class = question_registry[expected_object_type]
            else:
                # For other EDSL objects, use the broader registry
                edsl_registry = RegisterSubclassesMeta.get_registry()
                if expected_object_type not in edsl_registry:
                    return False
                object_class = edsl_registry[expected_object_type]

            # Try to instantiate the object from the dictionary
            if hasattr(object_class, "from_dict"):
                object_class.from_dict(answer_dict)
            else:
                # Fallback to direct instantiation
                object_class(**answer_dict)

            return True
        except Exception:
            return False


class QuestionEDSLObject(QuestionBase):
    """
    A question that expects a JSON representation of an EDSL object as an answer.

    This question type prompts an agent to provide a dictionary representation
    of an EDSL object that can be instantiated. The response is validated to
    ensure it can create the expected object type without exceptions.

    Attributes:
        question_type (str): Identifier for this question type, set to "edsl_object".
        expected_object_type (str): Name of the expected EDSL object class.
        _response_model: Pydantic model for validating responses.
        response_validator_class: Class used to validate and fix responses.

    Examples:
        >>> q = QuestionEDSLObject(
        ...     question_name="create_question",
        ...     question_text="Create a free text question about AI.",
        ...     expected_object_type="free_text"
        ... )
        >>> q.question_type
        'edsl_object'
        >>> q.expected_object_type
        'free_text'
    """

    question_type = "edsl_object"
    _response_model = EDSLObjectResponse
    response_validator_class = EDSLObjectResponseValidator

    def __init__(
        self,
        question_name: str,
        question_text: str,
        expected_object_type: str,
        answering_instructions: Optional[str] = None,
        question_presentation: Optional[str] = None,
    ):
        """
        Initialize a new EDSL object question.

        Args:
            question_name: Identifier for the question, used in results and templates.
                          Must be a valid Python variable name.
            question_text: The actual text of the question to be asked.
            expected_object_type: Name of the expected EDSL object type (e.g., "free_text").
            answering_instructions: Optional additional instructions for answering
                                    the question, overrides default instructions.
            question_presentation: Optional custom presentation template for the
                                  question, overrides default presentation.

        Raises:
            ValueError: If the expected_object_type is not found in the EDSL registry.

        Examples:
            >>> q = QuestionEDSLObject(
            ...     question_name="create_mc",
            ...     question_text="Create a multiple choice question about colors.",
            ...     expected_object_type="multiple_choice"
            ... )
            >>> q.expected_object_type
            'multiple_choice'
        """
        self.question_name = question_name
        self.question_text = question_text
        self._expected_object_type = expected_object_type
        self.answering_instructions = answering_instructions
        self.question_presentation = question_presentation

        # Validate that the expected object type exists in either registry
        question_registry = RegisterQuestionsMeta.question_types_to_classes()
        edsl_registry = RegisterSubclassesMeta.get_registry()

        if (
            expected_object_type not in question_registry
            and expected_object_type not in edsl_registry
        ):
            available_question_types = list(question_registry.keys())
            available_edsl_types = list(edsl_registry.keys())
            raise ValueError(
                f"Expected object type '{expected_object_type}' not found in EDSL registries. "
                f"Available question types: {available_question_types}. "
                f"Available EDSL types: {available_edsl_types}"
            )

    @property
    def expected_object_type(self) -> str:
        """Get the expected object type."""
        return self._expected_object_type

    def _validate_answer(self, answer: dict, replacement_dict: dict = None) -> dict:
        """
        Validate a raw answer against this question's constraints.

        This method extends the base validation to include EDSL object instantiation
        validation, ensuring the answer dictionary can create the expected object type.

        Args:
            answer: Dictionary containing the raw answer to validate.
            replacement_dict: Optional dictionary of replacements to apply during
                             validation for template variables.

        Returns:
            dict: A dictionary containing the validated answer.

        Raises:
            QuestionAnswerValidationError: If the answer fails validation.
        """
        # Handle the case where the model returns a raw EDSL object dict
        # (common with test models using canned_response)
        validator = self.response_validator

        # Check if this looks like a raw EDSL object response
        if isinstance(answer.get("answer"), dict):
            # Try direct validation of the raw answer dict first
            raw_answer = answer["answer"]
            if validator.validate_object_instantiation(
                raw_answer, self.expected_object_type
            ):
                # This is a valid EDSL object - use it directly
                return {
                    "answer": raw_answer,
                    "generated_tokens": answer.get("generated_tokens"),
                }

        # Check if the whole answer dict is actually an EDSL object
        # (when test service returns canned_response directly)
        if not answer.get("answer") and validator.validate_object_instantiation(
            answer, self.expected_object_type
        ):
            # The whole answer is the EDSL object
            return {
                "answer": answer,
                "generated_tokens": str(answer),  # Fallback for generated_tokens
            }

        # Fall back to standard validation
        validated_answer = super()._validate_answer(answer, replacement_dict)
        answer_dict = validated_answer["answer"]

        if not validator.validate_object_instantiation(
            answer_dict, self.expected_object_type
        ):
            from .exceptions import QuestionAnswerValidationError

            raise QuestionAnswerValidationError(
                message=f"Answer dictionary cannot be instantiated as {self.expected_object_type}",
                data=answer_dict,
                model=self._response_model,
                pydantic_error=None,
            )

        return validated_answer

    @property
    def question_html_content(self) -> str:
        """
        Generate HTML content for rendering the question in web interfaces.

        Returns:
            str: HTML markup for rendering the question.
        """
        from jinja2 import Template

        question_html_content = Template(
            """
        <div>
        <label for="{{ question_name }}">{{ expected_object_type }} JSON:</label>
        <textarea id="{{ question_name }}" name="{{ question_name }}"
                  placeholder="Enter JSON representation of {{ expected_object_type }}"></textarea>
        </div>
        """
        ).render(
            question_name=self.question_name,
            expected_object_type=self.expected_object_type,
        )
        return question_html_content

    @classmethod
    @inject_exception
    def example(cls, randomize: bool = False) -> "QuestionEDSLObject":
        """
        Create an example instance of an EDSL object question.

        Args:
            randomize: If True, appends a random UUID to the question text.

        Returns:
            QuestionEDSLObject: An example EDSL object question.

        Examples:
            >>> q = QuestionEDSLObject.example()
            >>> q.question_name
            'create_question'
            >>> q.expected_object_type
            'free_text'
        """
        addition = "" if not randomize else str(uuid4())
        return cls(
            question_name="create_question",
            question_text=f"Create a free text question about your favorite color.{addition}",
            expected_object_type="free_text",
        )

    def _simulate_answer(self, human_readable: bool = False) -> dict:
        """
        Generate a simulated valid answer for this question.

        Args:
            human_readable: Not used for EDSL object questions.

        Returns:
            dict: A dictionary containing a simulated valid answer.
        """
        # Create a real EDSL object and serialize it to get the proper format
        try:
            # First try question registry
            question_registry = RegisterQuestionsMeta.question_types_to_classes()
            object_class = question_registry.get(self.expected_object_type)
            # If not found in questions, try broader EDSL registry
            if object_class is None:
                edsl_registry = RegisterSubclassesMeta.get_registry()
                object_class = edsl_registry.get(self.expected_object_type)

            if object_class and hasattr(object_class, "example"):
                # Use the real example from the class
                real_example = object_class.example()
                simulated_object = real_example.to_dict()
            else:
                # Fallback for unknown types
                simulated_object = {
                    "object_type": self.expected_object_type,
                    "name": "example",
                    "edsl_version": "1.0.5.dev1",
                    "edsl_class_name": "Base",
                }
        except Exception:
            simulated_object = {
                "object_type": self.expected_object_type,
                "name": "example",
                "edsl_version": "1.0.5.dev1",
                "edsl_class_name": "Base",
            }

        return {
            "answer": simulated_object,
            "generated_tokens": json.dumps(simulated_object),
        }

    @classmethod
    def example_model(cls):
        """
        Create an example model with proper canned response for EDSL object questions.

        The canned response needs to be keyed by question_name for the test service.
        """
        from ..language_models import Model

        q = cls.example()
        simulated_answer = q._simulate_answer()

        # Create canned response keyed by question name
        canned_response = {q.question_name: simulated_answer["answer"]}

        return Model("test", canned_response=canned_response)


def main():
    """
    Demonstrate the functionality of the QuestionEDSLObject class.
    """
    from .question_edsl_object import QuestionEDSLObject

    # Create an example question
    q = QuestionEDSLObject.example()
    print(f"Question text: {q.question_text}")
    print(f"Question name: {q.question_name}")
    print(f"Expected object type: {q.expected_object_type}")

    # Simulate an answer
    simulated = q._simulate_answer()
    print(f"Simulated answer: {simulated}")

    # Validate the simulated answer
    validated = q._validate_answer(simulated)
    print(f"Validated answer: {validated}")

    print("EDSL Object question demonstration completed")


if __name__ == "__main__":
    main()
