from __future__ import annotations
from typing import Optional, List, Dict, Any, Union, Literal

from uuid import uuid4

from pydantic import field_validator, BaseModel


from .question_base import QuestionBase
from .response_validator_abc import ResponseValidatorABC
from .decorators import inject_exception


class InterviewerMessage(BaseModel):
    """
    Pydantic model for interviewer messages in an interview transcript.

    Attributes:
        role: The role of the speaker, always "interviewer".
        type: The type of message, always "message".
        text: The text content of the message.

    Examples:
        >>> msg = InterviewerMessage(text="How are you?")
        >>> msg.role
        'interviewer'
        >>> msg.type
        'message'
        >>> msg.text
        'How are you?'
    """

    role: Literal["interviewer"] = "interviewer"
    type: Literal["message"] = "message"
    text: str


class RespondentMessage(BaseModel):
    """
    Pydantic model for respondent messages in an interview transcript.

    Attributes:
        role: The role of the speaker, always "respondent".
        type: The type of message, always "message".
        text: The text content of the message.

    Examples:
        >>> msg = RespondentMessage(text="I'm doing well, thank you.")
        >>> msg.role
        'respondent'
        >>> msg.type
        'message'
        >>> msg.text
        "I'm doing well, thank you."
    """

    role: Literal["respondent"] = "respondent"
    type: Literal["message"] = "message"
    text: str


class InterviewResponse(BaseModel):
    """
    Pydantic model for validating interview responses.

    This model defines the structure and validation rules for responses to
    interview questions. It ensures that responses contain a valid interview
    transcript as a list of InterviewerMessage and RespondentMessage instances.

    Attributes:
        answer: The interview transcript as a list of message instances.
        generated_tokens: Optional raw LLM output for token tracking.

    Examples:
        >>> # Valid interview response
        >>> response = InterviewResponse(answer=[{"role": "interviewer", "text": "How are you?"}, {"role": "respondent", "text": "I'm doing well, thank you."}])
        >>> len(response.answer)
        2
        >>> response.answer[0].role
        'interviewer'

        >>> # Empty list is valid
        >>> response = InterviewResponse(answer=[])
        >>> response.answer
        []
    """

    answer: List[Union[InterviewerMessage, RespondentMessage]]
    generated_tokens: Optional[str] = None

    @field_validator("answer", mode="before")
    @classmethod
    def convert_answer_to_list(cls, v):
        """Convert answer to list to handle various response formats from language models."""
        if v is None:
            return []
        if isinstance(v, str):
            # Try to parse JSON string
            import json

            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
                # If it's a single dict, wrap it in a list
                if isinstance(parsed, dict):
                    return [parsed]
            except json.JSONDecodeError:
                pass
            # If string parsing fails, return empty list
            return []
        if isinstance(v, list):
            return v
        if isinstance(v, dict):
            # Single dict, wrap in list
            return [v]
        # For other types, try to convert to list
        return list(v) if hasattr(v, "__iter__") else []


class InterviewResponseValidator(ResponseValidatorABC):
    """
    Validator for interview question responses.

    This class implements the validation and fixing logic for interview responses.
    It ensures that responses contain a valid interview transcript as a list of
    dictionaries and provides methods to fix common issues in responses.

    Attributes:
        required_params: List of required parameters for validation.
        valid_examples: Examples of valid responses for testing.
        invalid_examples: Examples of invalid responses for testing.
    """

    required_params = []
    valid_examples = [
        (
            {
                "answer": [
                    {"role": "interviewer", "text": "Hello!"},
                    {"role": "respondent", "text": "Hi there!"},
                ]
            },
            {},
        )
    ]
    invalid_examples = [
        (
            {"answer": None},
            {},
            "Answer code must not be missing.",
        ),
    ]

    def _preprocess(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Preprocess the answer to add 'type': 'message' field to each message before validation.

        This method adds a "type" field with value "message" to each dict in the answer list
        before Pydantic validation occurs. This ensures the type field is present when
        the InterviewerMessage and RespondentMessage models validate the data.

        Args:
            data: The raw answer dictionary before validation.

        Returns:
            The preprocessed answer dictionary with "type": "message" added to each item.
        """
        answer = data.get("answer")
        if answer is not None and isinstance(answer, list):
            processed_answer = []
            for item in answer:
                if isinstance(item, dict):
                    # Create a copy and ensure type field is set
                    processed_item = item.copy()
                    if "type" not in processed_item:
                        processed_item["type"] = "message"
                    processed_answer.append(processed_item)
                else:
                    processed_answer.append(item)
            data["answer"] = processed_answer
        return data

    def fix(self, response: dict, verbose: bool = False) -> dict:
        """
        Fix common issues in interview responses.

        This method attempts to fix invalid responses by ensuring the answer
        field contains a valid list of dictionaries and is consistent with the
        generated_tokens field if present.

        Args:
            response: The response dictionary to fix.
            verbose: If True, print information about the fixing process.

        Returns:
            A fixed version of the response dictionary.
        """
        answer = response.get("answer")
        generated_tokens = response.get("generated_tokens")

        # Convert answer to list of dicts if needed
        if answer is None:
            answer = []
        elif isinstance(answer, str):
            # Try to parse JSON string
            import json

            try:
                parsed = json.loads(answer)
                if isinstance(parsed, list):
                    answer = parsed
                elif isinstance(parsed, dict):
                    answer = [parsed]
                else:
                    answer = []
            except json.JSONDecodeError:
                answer = []
        elif isinstance(answer, dict):
            # Single dict, wrap in list
            answer = [answer]
        elif not isinstance(answer, list):
            answer = []

        # Convert generated_tokens to list if it's a string
        if generated_tokens is not None and isinstance(generated_tokens, str):
            import json

            try:
                parsed = json.loads(generated_tokens)
                if isinstance(parsed, list):
                    generated_tokens_list = parsed
                elif isinstance(parsed, dict):
                    generated_tokens_list = [parsed]
                else:
                    generated_tokens_list = answer
            except json.JSONDecodeError:
                generated_tokens_list = answer
        else:
            generated_tokens_list = answer if generated_tokens is not None else None

        # If generated_tokens exists, prefer it over answer for consistency
        if generated_tokens_list is not None:
            return {
                "answer": generated_tokens_list,
                "generated_tokens": generated_tokens,
            }
        else:
            # If no generated_tokens, use the answer (converted to list)
            return {
                "answer": answer,
                "generated_tokens": None,
            }


class QuestionInterview(QuestionBase):
    """
    A question that simulates an interview dialogue between an interviewer and respondent.

    QuestionInterview prompts an agent to simulate a realistic interview transcript
    where the agent acts as the respondent being interviewed. The question_text provides
    the overall research question, while the interview_guide gives the interviewer
    specific topics or questions to explore during the conversation.

    The response should be formatted as a list of dictionaries, where each dictionary
    has "role" and "text" fields. The "role" field should be "interviewer" or "respondent",
    and these are automatically converted to "message" during post-processing.

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
                # Generate a random interview transcript as a list of dicts
                # Create 3-5 turns alternating between interviewer and respondent
                import random

                num_turns = random.randint(3, 5)
                answer_value = []
                for i in range(num_turns):
                    if i % 2 == 0:
                        role = "interviewer"
                        text = cls.__faker__.sentence()
                    else:
                        role = "respondent"
                        text = cls.__faker__.sentence()
                    answer_value.append({"role": role, "text": text})

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
        "answer": [
            {"role": "interviewer", "text": "How was your experience?"},
            {"role": "respondent", "text": "It was great!"},
        ],
        "generated_tokens": None,
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
