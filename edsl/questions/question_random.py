from __future__ import annotations
from typing import Optional, Any
import random

from pydantic import BaseModel

from .question_base import QuestionBase
from .response_validator_abc import ResponseValidatorABC
from .decorators import inject_exception


class RandomResponse(BaseModel):
    """
    Pydantic model for random question responses.

    Since random questions generate pseudo-random numbers directly,
    this model serves as a structured way to represent the output.

    Attributes:
        answer: A random number between 0 and 1
        comment: Optional comment about the result
        generated_tokens: Optional token usage data

    Examples:
        >>> # Valid response with a random number
        >>> response = RandomResponse(answer=0.42)
        >>> response.answer
        0.42

        >>> # Valid response with comment
        >>> response = RandomResponse(answer=0.789, comment="Random number generated")
        >>> response.answer
        0.789
    """

    answer: float
    comment: Optional[str] = None
    generated_tokens: Optional[Any] = None


class RandomResponseValidator(ResponseValidatorABC):
    """
    Validator for random question responses.

    Since random questions generate values directly without LLM inference,
    this validator is minimal and mainly serves for consistency with other question types.
    """

    required_params = []
    valid_examples = [
        ({"answer": 0.5}, {}),
        ({"answer": 0.123456, "comment": "Random value"}, {}),
    ]
    invalid_examples = []

    def fix(self, response, verbose=False):
        """
        Attempt to fix an invalid response.

        Since random questions generate values directly, this method is mainly
        for consistency with other question types.

        Args:
            response: The response to fix
            verbose: Whether to print verbose output

        Returns:
            The fixed response or the original response if it cannot be fixed
        """
        if verbose:
            print(f"Fixing random response: {response}")

        # Handle case where response is a raw value without the proper structure
        if not isinstance(response, dict):
            try:
                return {"answer": float(response)}
            except Exception as e:
                if verbose:
                    print(f"Failed to fix response: {e}")
                return {"answer": 0.0, "comment": "Failed to generate random number"}

        return response


class QuestionRandom(QuestionBase):
    """
    A question that generates a pseudo-random number between 0 and 1.

    QuestionRandom is a special type of question that does not require LLM inference.
    Instead, it directly generates a pseudo-random number using Python's random.random()
    function. This is useful for randomization in surveys, A/B testing, or any scenario
    requiring random values.

    The random number generation uses Python's global random state. For reproducible
    results across a survey run, set the seed at the session level using random.seed()
    before running your survey.

    Attributes:
        question_type (str): Identifier for this question type, set to "random".
        _response_model: Initially None, set by create_response_model().
        response_validator_class: Class used to validate and fix responses.

    Examples:
        >>> # Create a basic random question
        >>> q = QuestionRandom(question_name="random_value")
        >>> q.question_name
        'random_value'

        >>> # Generate answer directly
        >>> import random
        >>> random.seed(42)  # Set seed at session level for reproducibility
        >>> q = QuestionRandom(question_name="test_random")
        >>> answer = q.answer_question_directly({})
        >>> 0 <= answer['answer'] <= 1
        True

        >>> # Multiple questions will get different random values
        >>> random.seed(100)
        >>> q1 = QuestionRandom(question_name="rand1")
        >>> q2 = QuestionRandom(question_name="rand2")
        >>> a1 = q1.answer_question_directly()
        >>> a2 = q2.answer_question_directly()
        >>> a1['answer'] != a2['answer']  # Different random values
        True
    """

    question_type = "random"

    _response_model = None
    response_validator_class = RandomResponseValidator

    def __init__(
        self,
        question_name: str,
        question_text: Optional[str] = None,
        question_presentation: Optional[str] = None,
        answering_instructions: Optional[str] = None,
    ):
        """
        Initialize a new random question.

        Args:
            question_name: Identifier for the question, used in results and templates.
                          Must be a valid Python variable name.
            question_text: Optional text description of the question.
                          Defaults to "Random number generator".
            question_presentation: Optional custom presentation template.
            answering_instructions: Optional additional instructions.

        Note:
            For reproducible random numbers, set the seed at the session level
            using random.seed() before running your survey.

        Examples:
            >>> q = QuestionRandom(question_name="rand1")
            >>> q.question_name
            'rand1'

            >>> q = QuestionRandom(question_name="rand2", question_text="Generate a random value")
            >>> q.question_text
            'Generate a random value'
        """
        super().__init__()
        self.question_name = question_name
        self.question_text = question_text or "Random number generator"
        self.question_presentation = question_presentation
        self.answering_instructions = answering_instructions

    def create_response_model(self):
        """
        Create a response model for random question responses.

        Returns:
            The RandomResponse Pydantic model class.

        Examples:
            >>> q = QuestionRandom.example()
            >>> model = q.create_response_model()
            >>> response = model(answer=0.5)
            >>> response.answer
            0.5
        """
        return RandomResponse

    def answer_question_directly(self, scenario=None, agent_traits=None):
        """
        Generate a random number between 0 and 1.

        This method directly generates the answer without LLM inference.
        Each call returns the next value from Python's random number generator.

        Args:
            scenario: Not used, but included for compatibility with base class.
            agent_traits: Not used, but included for compatibility with base class.

        Returns:
            A dictionary with the random number as the answer.

        Examples:
            >>> import random
            >>> random.seed(42)
            >>> q = QuestionRandom(question_name="test")
            >>> answer = q.answer_question_directly()
            >>> 0 <= answer['answer'] <= 1
            True
            >>> isinstance(answer['answer'], float)
            True
        """
        result = {"answer": random.random(), "comment": None}

        # Validate the result using the Pydantic model
        return self.create_response_model()(**result).model_dump()

    def _simulate_answer(self, human_readable: bool = False) -> dict:
        """
        Generate a simulated random answer.

        This is essentially the same as answer_question_directly for random questions.

        Args:
            human_readable: Flag for human-readable output (not used for random questions)

        Returns:
            A dictionary with a random number between 0 and 1

        Examples:
            >>> import random
            >>> random.seed(42)
            >>> q = QuestionRandom(question_name="test")
            >>> answer = q._simulate_answer()
            >>> 0 <= answer['answer'] <= 1
            True
        """
        return self.answer_question_directly()

    def _validate_answer(self, answer: dict) -> dict:
        """
        Validate the answer using the Pydantic model.

        Args:
            answer: Dictionary containing the answer to validate

        Returns:
            Validated answer dictionary

        Examples:
            >>> q = QuestionRandom(question_name="test")
            >>> answer = {"answer": 0.5}
            >>> validated = q._validate_answer(answer)
            >>> validated['answer']
            0.5
        """
        try:
            return self.create_response_model()(**answer).model_dump()
        except Exception as e:
            from pydantic import ValidationError
            from .exceptions import QuestionAnswerValidationError

            # Create a ValidationError with a helpful message
            validation_error = ValidationError.from_exception_data(
                title="RandomResponse",
                line_errors=[
                    {
                        "type": "value_error",
                        "loc": ("answer",),
                        "msg": f"Random response validation failed: {str(e)}",
                        "input": answer,
                        "ctx": {"error": str(e)},
                    }
                ],
            )
            raise QuestionAnswerValidationError(
                message=f"Invalid random response: {str(e)}",
                data=answer,
                model=self.create_response_model(),
                pydantic_error=validation_error,
            )

    @property
    def question_html_content(self) -> str:
        """
        Generate HTML content for rendering the question in web interfaces.

        Returns:
            str: HTML markup for rendering the question.

        Examples:
            >>> q = QuestionRandom(question_name="test_random")
            >>> html = q.question_html_content
            >>> 'test_random' in html
            True
        """
        from jinja2 import Template

        question_html_content = Template(
            """
        <div>
        <input type="number" id="{{ question_name }}" name="{{ question_name }}"
               step="any" min="0" max="1" readonly value="random">
        </div>
        """
        ).render(question_name=self.question_name)
        return question_html_content

    @classmethod
    @inject_exception
    def example(cls) -> QuestionRandom:
        """
        Create an example instance of a random question.

        This class method creates a predefined example of a random question
        for demonstration, testing, and documentation purposes.

        Returns:
            QuestionRandom: An example random question.

        Examples:
            >>> q = QuestionRandom.example()
            >>> q.question_name
            'random_number'
            >>> q.question_text
            'Generate a pseudo-random number between 0 and 1'
        """
        return cls(
            question_name="random_number",
            question_text="Generate a pseudo-random number between 0 and 1",
        )


def main():
    """
    Demonstrate the functionality of the QuestionRandom class.

    This function creates an example random question and demonstrates its
    key features including answer generation, validation, and serialization.
    It's primarily intended for testing and development purposes.
    """
    # Set seed for reproducibility in the demo
    random.seed(42)

    # Create an example question
    q = QuestionRandom.example()
    print(f"Question text: {q.question_text}")
    print(f"Question name: {q.question_name}")

    # Generate a random answer
    answer = q.answer_question_directly()
    print(f"Generated answer: {answer}")

    # Generate multiple answers to show they're different
    answer2 = q.answer_question_directly()
    print(f"Second generated answer: {answer2}")

    # Validate an answer
    valid_answer = {"answer": 0.789}
    validated = q._validate_answer(valid_answer)
    print(f"Validated answer: {validated}")

    # Simulate an answer
    simulated = q._simulate_answer()
    print(f"Simulated answer: {simulated}")

    # Serialization demonstration
    serialized = q.to_dict()
    print(f"Serialized: {serialized}")
    deserialized = QuestionBase.from_dict(serialized)
    print(
        f"Deserialization successful: {deserialized.question_text == q.question_text}"
    )

    # Run doctests
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
    print("Doctests completed")


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)

    # Uncomment to run demonstration
    # main()
