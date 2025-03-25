from __future__ import annotations
from typing import Optional

from uuid import uuid4

from pydantic import model_validator, BaseModel, ValidationError


from .question_base import QuestionBase
from .response_validator_abc import ResponseValidatorABC
from .decorators import inject_exception


class FreeTextResponse(BaseModel):
    """
    Pydantic model for validating free text responses.
    
    This model defines the structure and validation rules for responses to
    free text questions. It ensures that responses contain a valid text string
    and that the answer and generated_tokens fields match when both are present.
    
    Attributes:
        answer: The text response string.
        generated_tokens: Optional raw LLM output for token tracking.

    Examples:
        >>> # Valid response with just answer
        >>> response = FreeTextResponse(answer="Hello world")
        >>> response.answer
        'Hello world'

        >>> # Valid response with matching tokens
        >>> response = FreeTextResponse(answer="Hello world", generated_tokens="Hello world")
        >>> response.answer
        'Hello world'

        >>> # Invalid response with mismatched tokens
        >>> try:
        ...     FreeTextResponse(answer="Hello world", generated_tokens="Different text")
        ... except Exception as e:
        ...     print("Validation error occurred")
        Validation error occurred

        >>> # Empty string is valid
        >>> response = FreeTextResponse(answer="")
        >>> response.answer
        ''
    """

    answer: str
    generated_tokens: Optional[str] = None

    @model_validator(mode='after')
    def validate_tokens_match_answer(self):
        """
        Validate that the answer matches the generated tokens if provided.
        
        This validator ensures consistency between the answer and generated_tokens
        fields when both are present. They must match exactly.
        
        Returns:
            The validated model instance.
            
        Raises:
            ValueError: If the answer and generated_tokens don't match exactly.
        """
        if self.generated_tokens is not None:
            if self.answer.strip() != self.generated_tokens.strip():
                from .exceptions import QuestionAnswerValidationError
                validation_error = ValidationError.from_exception_data(
                    title='FreeTextResponse',
                    line_errors=[{
                        'type': 'value_error',
                        'loc': ('answer', 'generated_tokens'),
                        'msg': 'Values must match',
                        'input': self.generated_tokens,
                        'ctx': {'error': 'Values do not match'}
                    }]
                )
                raise QuestionAnswerValidationError(
                    message=f"answer '{self.answer}' must exactly match generated_tokens '{self.generated_tokens}'",
                    data=self.model_dump(),
                    model=self.__class__,
                    pydantic_error=validation_error
                )
        return self


class FreeTextResponseValidator(ResponseValidatorABC):
    """
    Validator for free text question responses.
    
    This class implements the validation and fixing logic for free text responses.
    It ensures that responses contain a valid text string and provides methods
    to fix common issues in responses.
    
    Attributes:
        required_params: List of required parameters for validation.
        valid_examples: Examples of valid responses for testing.
        invalid_examples: Examples of invalid responses for testing.

    Examples:
        >>> from edsl import QuestionFreeText
        >>> q = QuestionFreeText.example()
        >>> validator = q.response_validator

        >>> # Fix mismatched tokens by using generated_tokens
        >>> response = {"answer": "Hello", "generated_tokens": "Goodbye"}
        >>> fixed = validator.fix(response)
        >>> fixed
        {'answer': 'Goodbye', 'generated_tokens': 'Goodbye'}

        >>> # Handle None values by converting to strings
        >>> response = {"answer": None, "generated_tokens": "Some text"}
        >>> fixed = validator.fix(response)
        >>> fixed
        {'answer': 'Some text', 'generated_tokens': 'Some text'}

        >>> # Validate fixed response
        >>> validated = validator.validate(fixed)
        >>> validated['answer'] == validated['generated_tokens']
        True

        >>> # Fix when only generated_tokens is present
        >>> response = {"generated_tokens": "Solo tokens"}
        >>> fixed = validator.fix(response)
        >>> fixed['answer'] == fixed['generated_tokens'] == "Solo tokens"
        True
    """

    required_params = []
    valid_examples = [({"answer": "This is great"}, {})]
    invalid_examples = [
        (
            {"answer": None},
            {},
            "Answer code must not be missing.",
        ),
    ]

    def fix(self, response: dict, verbose: bool = False) -> dict:
        """
        Fix common issues in free text responses.
        
        This method attempts to fix invalid responses by ensuring the answer
        field contains a valid string and is consistent with the generated_tokens
        field if present.
        
        Args:
            response: The response dictionary to fix.
            verbose: If True, print information about the fixing process.
            
        Returns:
            A fixed version of the response dictionary.
            
        Notes:
            - For free text responses, the answer is always synchronized with generated_tokens
            - Both fields are converted to strings to ensure type consistency
        """
        if response.get("generated_tokens") != response.get("answer"):
            return {
                "answer": str(response.get("generated_tokens")),
                "generated_tokens": str(response.get("generated_tokens")),
            }
        else:
            return {
                "answer": str(response.get("generated_tokens")),
                "generated_tokens": str(response.get("generated_tokens")),
            }


class QuestionFreeText(QuestionBase):
    """
    A question that allows an agent to respond with free-form text.
    
    QuestionFreeText is one of the simplest and most commonly used question types
    in EDSL. It prompts an agent or language model to provide a textual response
    without any specific structure or constraints on the format. The response can
    be of any length and content, making it suitable for open-ended questions,
    explanations, storytelling, and other scenarios requiring unrestricted text.
    
    Attributes:
        question_type (str): Identifier for this question type, set to "free_text".
        _response_model: Pydantic model for validating responses.
        response_validator_class: Class used to validate and fix responses.

    Examples:
        >>> q = QuestionFreeText(
        ...     question_name="opinion", 
        ...     question_text="What do you think about AI?"
        ... )
        >>> q.question_type
        'free_text'
        
        >>> from edsl.language_models import Model
        >>> model = Model("test", canned_response="I think AI is fascinating.")
        >>> result = q.by(model).run(disable_remote_inference=True)
        >>> answer = result.select("answer.*").to_list()[0]
        >>> "fascinating" in answer
        True
    """

    question_type = "free_text"
    _response_model = FreeTextResponse
    response_validator_class = FreeTextResponseValidator

    def __init__(
        self,
        question_name: str,
        question_text: str,
        answering_instructions: Optional[str] = None,
        question_presentation: Optional[str] = None,
    ):
        """
        Initialize a new free text question.
        
        Args:
            question_name: Identifier for the question, used in results and templates.
                          Must be a valid Python variable name.
            question_text: The actual text of the question to be asked.
            answering_instructions: Optional additional instructions for answering
                                    the question, overrides default instructions.
            question_presentation: Optional custom presentation template for the
                                  question, overrides default presentation.
                                  
        Examples:
            >>> q = QuestionFreeText(
            ...     question_name="feedback",
            ...     question_text="Please provide your thoughts on this product."
            ... )
            >>> q.question_name
            'feedback'
            
            >>> q = QuestionFreeText(
            ...     question_name="explanation",
            ...     question_text="Explain how photosynthesis works.",
            ...     answering_instructions="Provide a detailed scientific explanation."
            ... )
        """
        self.question_name = question_name
        self.question_text = question_text
        self.answering_instructions = answering_instructions
        self.question_presentation = question_presentation

    @property
    def question_html_content(self) -> str:
        """
        Generate HTML content for rendering the question in web interfaces.
        
        This property generates HTML markup for the question when it needs to be
        displayed in web interfaces or HTML contexts. For a free text question,
        this is typically a textarea element.
        
        Returns:
            str: HTML markup for rendering the question.
            
        Notes:
            - Uses Jinja2 templating to generate the HTML
            - Creates a textarea input element with the question_name as the ID and name
            - Can be used for displaying the question in web UIs or HTML exports
        """
        from jinja2 import Template

        question_html_content = Template(
            """
        <div>
        <textarea id="{{ question_name }}" name="{{ question_name }}"></textarea>
        </div>
        """
        ).render(question_name=self.question_name)
        return question_html_content

    @classmethod
    @inject_exception
    def example(cls, randomize: bool = False) -> "QuestionFreeText":
        """
        Create an example instance of a free text question.
        
        This class method creates a predefined example of a free text question
        for demonstration, testing, and documentation purposes.
        
        Args:
            randomize: If True, appends a random UUID to the question text to
                     ensure uniqueness in tests and examples.
                     
        Returns:
            QuestionFreeText: An example free text question.
            
        Examples:
            >>> q = QuestionFreeText.example()
            >>> q.question_name
            'how_are_you'
            >>> q.question_text
            'How are you?'
            
            >>> q1 = QuestionFreeText.example(randomize=True)
            >>> q2 = QuestionFreeText.example(randomize=True)
            >>> q1.question_text != q2.question_text
            True
        """
        addition = "" if not randomize else str(uuid4())
        return cls(question_name="how_are_you", question_text=f"How are you?{addition}")


def main():
    """
    Demonstrate the functionality of the QuestionFreeText class.
    
    This function creates an example free text question and demonstrates its
    key features including validation, serialization, and answer simulation.
    It's primarily intended for testing and development purposes.
    
    Note:
        This function will be executed when the module is run directly,
        but not when imported.
    """
    from .question_free_text import QuestionFreeText

    # Create an example question
    q = QuestionFreeText.example()
    print(f"Question text: {q.question_text}")
    print(f"Question name: {q.question_name}")
    
    # Validate an answer
    valid_answer = {"answer": "I like custard", "generated_tokens": "I like custard"}
    validated = q._validate_answer(valid_answer)
    print(f"Validated answer: {validated}")
    
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
 