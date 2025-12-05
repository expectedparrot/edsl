from __future__ import annotations
from typing import Optional

from uuid import uuid4

from pydantic import model_validator, field_validator, BaseModel, ValidationError


from .question_base import QuestionBase
from .response_validator_abc import ResponseValidatorABC
from .decorators import inject_exception


class InterviewResponse(BaseModel):
    """
    Pydantic model for validating interview responses.

    This model defines the structure and validation rules for responses to
    interview questions. It ensures that responses contain a valid interview
    transcript string with dialogue between interviewer and respondent.

    Attributes:
        answer: The interview transcript as a string with newline-separated dialogue.
        generated_tokens: Optional raw LLM output for token tracking.

    Examples:
        >>> # Valid interview response
        >>> response = InterviewResponse(answer="Interviewer: How are you?\\nRespondent: I'm doing well, thank you.")
        >>> "Interviewer:" in response.answer
        True

        >>> # Empty string is valid
        >>> response = InterviewResponse(answer="")
        >>> response.answer
        ''
    """

    answer: str
    generated_tokens: Optional[str] = None

    @field_validator("answer", mode="before")
    @classmethod
    def convert_answer_to_string(cls, v):
        """Convert answer to string to handle non-string responses from language models."""
        if v is not None:
            return str(v)
        return v

    @model_validator(mode="after")
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
                    title="InterviewResponse",
                    line_errors=[
                        {
                            "type": "value_error",
                            "loc": ("answer", "generated_tokens"),
                            "msg": "Values must match",
                            "input": self.generated_tokens,
                            "ctx": {"error": "Values do not match"},
                        }
                    ],
                )
                raise QuestionAnswerValidationError(
                    message=f"answer '{self.answer}' must exactly match generated_tokens '{self.generated_tokens}'",
                    data=self.model_dump(),
                    model=self.__class__,
                    pydantic_error=validation_error,
                )
        return self


class InterviewResponseValidator(ResponseValidatorABC):
    """
    Validator for interview question responses.

    This class implements the validation and fixing logic for interview responses.
    It ensures that responses contain a valid interview transcript string and
    provides methods to fix common issues in responses.

    Attributes:
        required_params: List of required parameters for validation.
        valid_examples: Examples of valid responses for testing.
        invalid_examples: Examples of invalid responses for testing.
    """

    required_params = []
    valid_examples = [({"answer": "Interviewer: Hello!\nRespondent: Hi there!"}, {})]
    invalid_examples = [
        (
            {"answer": None},
            {},
            "Answer code must not be missing.",
        ),
    ]

    def fix(self, response: dict, verbose: bool = False) -> dict:
        """
        Fix common issues in interview responses.

        This method attempts to fix invalid responses by ensuring the answer
        field contains a valid string and is consistent with the generated_tokens
        field if present.

        Args:
            response: The response dictionary to fix.
            verbose: If True, print information about the fixing process.

        Returns:
            A fixed version of the response dictionary.
        """
        # Convert both answer and generated_tokens to strings to handle integer responses
        answer = response.get("answer")
        generated_tokens = response.get("generated_tokens")

        # Convert answer to string if it's not None
        if answer is not None:
            answer = str(answer)

        # Convert generated_tokens to string if it's not None
        if generated_tokens is not None:
            generated_tokens = str(generated_tokens)

        # If generated_tokens exists, prefer it over answer for consistency
        if generated_tokens is not None:
            return {
                "answer": generated_tokens,
                "generated_tokens": generated_tokens,
            }
        else:
            # If no generated_tokens, use the answer (converted to string)
            return {
                "answer": answer or "",
                "generated_tokens": None,
            }


class QuestionInterview(QuestionBase):
    """
    A question that simulates an interview dialogue between an interviewer and respondent.

    QuestionInterview prompts an agent to simulate a realistic interview transcript
    where the agent acts as the respondent being interviewed. The question_text provides
    the overall research question, while the interview_guide gives the interviewer
    specific topics or questions to explore during the conversation.

    The response should be formatted as a newline-separated dialogue between
    "Interviewer:" and "Respondent:", going back and forth to create a realistic
    interview transcript.

    Attributes:
        question_type (str): Identifier for this question type, set to "interview".
        _response_model: Pydantic model for validating responses.
        response_validator_class: Class used to validate and fix responses.
        interview_guide (str): Instructions or topics to guide the interviewer.

    Examples:
        >>> q = QuestionInterview(
        ...     question_name="user_experience",
        ...     question_text="Understanding user satisfaction with mobile apps",
        ...     interview_guide="Ask about their daily usage, favorite features, pain points, and suggestions for improvement."
        ... )
        >>> q.question_type
        'interview'
        >>> "mobile apps" in q.question_text
        True
        >>> "pain points" in q.interview_guide
        True
    """

    question_type = "interview"
    _response_model = InterviewResponse
    response_validator_class = InterviewResponseValidator

    def __init__(
        self,
        question_name: str,
        question_text: str,
        interview_guide: str,
        answering_instructions: Optional[str] = None,
        question_presentation: Optional[str] = None,
    ):
        """
        Initialize a new interview question.

        Args:
            question_name: Identifier for the question, used in results and templates.
                          Must be a valid Python variable name.
            question_text: The overall research question or topic for the interview.
            interview_guide: Instructions, topics, or specific questions to guide
                           the interviewer during the conversation.
            answering_instructions: Optional additional instructions for answering
                                    the question, overrides default instructions.
            question_presentation: Optional custom presentation template for the
                                  question, overrides default presentation.

        Examples:
            >>> q = QuestionInterview(
            ...     question_name="product_feedback",
            ...     question_text="Gather feedback on our new product feature",
            ...     interview_guide="Focus on usability, first impressions, and comparison to competitors."
            ... )
            >>> q.question_name
            'product_feedback'
            >>> q.interview_guide
            'Focus on usability, first impressions, and comparison to competitors.'
        """
        self.question_name = question_name
        self.question_text = question_text
        self.interview_guide = interview_guide
        self.answering_instructions = answering_instructions
        self.question_presentation = question_presentation

    @property
    def question_html_content(self) -> str:
        """
        Generate HTML content for rendering the question in web interfaces.

        This property generates HTML markup for the question when it needs to be
        displayed in web interfaces or HTML contexts. For an interview question,
        this includes the research question, interview guide, and a large textarea
        for the interview transcript.

        Returns:
            str: HTML markup for rendering the question.
        """
        from jinja2 import Template

        question_html_content = Template(
            """
        <div class="interview-question">
            <h3>Research Question:</h3>
            <p>{{ question_text }}</p>
            <h3>Interview Guide:</h3>
            <p>{{ interview_guide }}</p>
            <h3>Interview Transcript:</h3>
            <textarea id="{{ question_name }}" name="{{ question_name }}" rows="20" cols="80" placeholder="Interviewer: [Start the interview...]
Respondent: [Your response...]
Interviewer: [Follow-up question...]
Respondent: [Your response...]"></textarea>
        </div>
        """
        ).render(
            question_name=self.question_name,
            question_text=self.question_text,
            interview_guide=self.interview_guide,
        )
        return question_html_content

    @property
    def fake_data_factory(self):
        """
        Custom factory for generating fake interview data.

        Ensures answer and generated_tokens are consistent when both present.
        """
        from polyfactory.factories.pydantic_factory import ModelFactory

        class ConsistentInterviewResponseFactory(ModelFactory[InterviewResponse]):
            __model__ = InterviewResponse

            @classmethod
            def build(cls, **kwargs):
                """Generate consistent answer and generated_tokens."""
                # Generate a random answer first
                answer_value = cls.__faker__.text()

                # Create the model with consistent values to avoid validation error
                return cls.__model__(
                    answer=answer_value,
                    generated_tokens=None,  # Keep generated_tokens as None to avoid mismatch
                )

        return ConsistentInterviewResponseFactory

    @property
    def data(self) -> dict:
        """Return a dictionary of question attributes including interview_guide."""
        # Get the base data from parent class
        base_data = super().data

        # Add interview_guide to the data
        base_data["interview_guide"] = self.interview_guide

        return base_data

    @classmethod
    @inject_exception
    def example(cls, randomize: bool = False) -> "QuestionInterview":
        """
        Create an example instance of an interview question.

        This class method creates a predefined example of an interview question
        for demonstration, testing, and documentation purposes.

        Args:
            randomize: If True, appends a random UUID to the question text to
                     ensure uniqueness in tests and examples.

        Returns:
            QuestionInterview: An example interview question.

        Examples:
            >>> q = QuestionInterview.example()
            >>> q.question_name
            'customer_experience'
            >>> "customer service" in q.question_text
            True
            >>> "experience" in q.interview_guide
            True
        """
        addition = "" if not randomize else str(uuid4())
        return cls(
            question_name="customer_experience",
            question_text=f"Understanding customer satisfaction with our customer service{addition}",
            interview_guide="Ask about their recent interactions, what went well, areas for improvement, and overall satisfaction rating.",
        )


def main():
    """
    Demonstrate the functionality of the QuestionInterview class.

    This function creates an example interview question and demonstrates its
    key features including validation, serialization, and answer simulation.
    It's primarily intended for testing and development purposes.
    """
    from .question_interview import QuestionInterview

    # Create an example question
    q = QuestionInterview.example()
    print(f"Question text: {q.question_text}")
    print(f"Question name: {q.question_name}")
    print(f"Interview guide: {q.interview_guide}")

    # Validate an answer
    valid_answer = {
        "answer": "Interviewer: How was your experience?\nRespondent: It was great!",
        "generated_tokens": "Interviewer: How was your experience?\nRespondent: It was great!",
    }
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
