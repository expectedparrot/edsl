"""Question type for direct LLM calls that bypass normal EDSL agent/prompt processing.

This module provides the QuestionInterviewerThinking class, which allows users to make
direct LLM calls with custom user and system prompts, bypassing the normal EDSL job
execution flow that builds prompts from agents and scenarios.

Key features:
- Direct LLM calls without agent persona injection
- Embedded model specification (the question carries its own model)
- Optional Pydantic model support for structured JSON outputs
- Still uses the cache system for reproducibility
- Supports Jinja2 templating to reference previous answers

Use cases:
- Generating follow-up questions based on previous responses
- Performing meta-level analysis on survey responses
- Any scenario where you need direct LLM access without agent framing
"""

from __future__ import annotations
from typing import Optional, Type, Any, Union
from uuid import uuid4

from pydantic import BaseModel, field_validator

from .question_base import QuestionBase
from .response_validator_abc import ResponseValidatorABC
from .decorators import inject_exception


class InterviewerThinkingResponse(BaseModel):
    """
    Pydantic model for validating interviewer thinking responses.

    This model defines the structure for responses to interviewer thinking questions.
    It supports both free-text responses (string) and structured responses (dict)
    when a response_model is provided.

    Attributes:
        answer: The response - either a string (free text) or dict (structured output)
        generated_tokens: Optional raw LLM output for token tracking

    Examples:
        >>> # Valid free-text response
        >>> response = InterviewerThinkingResponse(answer="What's your favorite color?")
        >>> response.answer
        "What's your favorite color?"

        >>> # Valid structured response
        >>> response = InterviewerThinkingResponse(answer={"question": "Why?", "category": "follow-up"})
        >>> response.answer
        {'question': 'Why?', 'category': 'follow-up'}
    """

    answer: Union[str, dict, list]
    generated_tokens: Optional[str] = None

    @field_validator("answer", mode="before")
    @classmethod
    def convert_answer(cls, v):
        """Convert answer to appropriate type."""
        if v is None:
            return ""
        return v


class InterviewerThinkingResponseValidator(ResponseValidatorABC):
    """
    Validator for interviewer thinking question responses.

    This validator is minimal since:
    - For free-text mode, we accept any string response
    - For structured output mode, we trust the model's structured output capability
      (pass-through validation)
    """

    required_params = []
    valid_examples = [
        ({"answer": "What is your favorite food?"}, {}),
        ({"answer": {"question": "Why do you like that?", "topic": "preferences"}}, {}),
    ]
    invalid_examples = []

    def fix(self, response: dict, verbose: bool = False) -> dict:
        """
        Fix common issues in responses.

        For interviewer thinking questions, we primarily ensure the answer field exists.
        """
        answer = response.get("answer")
        generated_tokens = response.get("generated_tokens")

        # If answer is None but generated_tokens exists, use generated_tokens
        if answer is None and generated_tokens is not None:
            # Try to parse as JSON for structured output
            import json

            try:
                answer = json.loads(generated_tokens)
            except (json.JSONDecodeError, TypeError):
                answer = generated_tokens

        # Ensure we have some answer
        if answer is None:
            answer = ""

        return {
            "answer": answer,
            "generated_tokens": generated_tokens,
        }


class QuestionInterviewerThinking(QuestionBase):
    """
    A question type that makes direct LLM calls bypassing normal EDSL agent/prompt processing.

    Unlike regular EDSL questions that are framed as being presented to an agent with
    persona and instructions, QuestionInterviewerThinking makes direct calls to an LLM
    with user-specified prompts. This is useful for "meta-level" operations like
    analyzing responses or generating follow-up questions.

    Key differences from regular questions:
    - Does NOT use agent personas or agent instructions
    - Uses question_text directly as the user prompt
    - Has an optional system_prompt parameter
    - Embeds its own model (ignores the job/survey's model)
    - Still uses the cache system for reproducibility

    Attributes:
        question_type (str): Identifier for this question type, set to "interviewer_thinking"
        question_name (str): Identifier for the question instance
        question_text (str): The user prompt to send to the LLM
        system_prompt (Optional[str]): Optional system prompt
        model_dict (dict): The model configuration, serialized from a Model instance
        response_model (Optional[Type[BaseModel]]): Optional Pydantic model for structured outputs

    Examples:
        Basic usage (free text output):

        >>> from edsl import Model
        >>> q = QuestionInterviewerThinking(
        ...     question_name="follow_up",
        ...     question_text="The user said they like pizza. What's a good follow-up question?",
        ...     model=Model("gpt-4o")
        ... )
        >>> q.question_type
        'interviewer_thinking'

        With Jinja2 templating to reference previous answers:

        >>> q = QuestionInterviewerThinking(
        ...     question_name="analyze",
        ...     question_text="The subject responded {{ q1.answer }}. Generate a follow-up.",
        ...     system_prompt="You are a helpful survey researcher.",
        ...     model=Model("gpt-4o")
        ... )

        With structured output using Pydantic model:

        >>> from pydantic import BaseModel
        >>> class FollowUp(BaseModel):
        ...     question: str
        ...     reasoning: str
        >>> q = QuestionInterviewerThinking(
        ...     question_name="structured_follow_up",
        ...     question_text="Generate a follow-up question for: {{ q1.answer }}",
        ...     model=Model("gpt-4o"),
        ...     response_model=FollowUp
        ... )
    """

    question_type = "interviewer_thinking"
    _response_model = InterviewerThinkingResponse
    response_validator_class = InterviewerThinkingResponseValidator

    def __init__(
        self,
        question_name: str,
        question_text: str,
        model: Any,  # Model instance or dict
        system_prompt: Optional[str] = None,
        response_model: Optional[Type[BaseModel]] = None,
        answering_instructions: Optional[str] = None,
        question_presentation: Optional[str] = None,
    ):
        """
        Initialize a new interviewer thinking question.

        Args:
            question_name: Identifier for the question, used in results and templates.
                          Must be a valid Python variable name.
            question_text: The user prompt to send to the LLM. Supports Jinja2 templating
                          for referencing previous answers (e.g., {{ q1.answer }}).
            model: The Model instance to use for this question. This model will be used
                   regardless of what model is specified at the job/survey level.
                   Can be a Model instance or a dict (for deserialization).
            system_prompt: Optional system prompt to send to the LLM.
            response_model: Optional Pydantic model class for structured JSON output.
                           When provided, the model's schema will be passed to the LLM.
            answering_instructions: Not used for this question type (kept for compatibility).
            question_presentation: Not used for this question type (kept for compatibility).
        """
        self.question_name = question_name
        self.question_text = question_text
        self._system_prompt = system_prompt or ""
        self._user_response_model = response_model
        self.answering_instructions = answering_instructions
        self.question_presentation = question_presentation

        # Store the model - either as dict or convert from Model instance
        if isinstance(model, dict):
            self._model_dict = model
        else:
            # Assume it's a Model instance
            self._model_dict = model.to_dict(add_edsl_version=False)

    @property
    def system_prompt(self) -> str:
        """Get the system prompt."""
        return self._system_prompt

    @system_prompt.setter
    def system_prompt(self, value: str):
        """Set the system prompt."""
        self._system_prompt = value or ""

    @property
    def model_dict(self) -> dict:
        """Get the serialized model configuration."""
        return self._model_dict

    @property
    def user_response_model(self) -> Optional[Type[BaseModel]]:
        """Get the user-specified Pydantic response model for structured outputs."""
        return self._user_response_model

    def get_model(self):
        """
        Get a Model instance from the stored model configuration.

        Returns:
            LanguageModel: A Model instance ready for use.
        """
        from ..language_models import LanguageModel

        return LanguageModel.from_dict(self._model_dict)

    def get_response_schema(self) -> Optional[dict]:
        """
        Get the JSON schema for structured output if response_model is specified.

        Returns:
            dict or None: The JSON schema from the Pydantic model, or None if not specified.
        """
        if self._user_response_model is not None:
            return self._user_response_model.model_json_schema()
        return None

    @property
    def question_html_content(self) -> str:
        """
        Generate HTML content for rendering the question in web interfaces.

        For interviewer thinking questions, this shows the prompt that will be sent.
        """
        from jinja2 import Template

        html = Template(
            """
        <div class="interviewer-thinking-question">
            <h3>User Prompt:</h3>
            <p>{{ question_text }}</p>
            {% if system_prompt %}
            <h3>System Prompt:</h3>
            <p>{{ system_prompt }}</p>
            {% endif %}
            <h3>Model:</h3>
            <p>{{ model_name }}</p>
        </div>
        """
        ).render(
            question_text=self.question_text,
            system_prompt=self._system_prompt,
            model_name=self._model_dict.get("model", "Unknown"),
        )
        return html

    @property
    def data(self) -> dict:
        """Return a dictionary of question attributes."""
        base_data = {
            "question_name": self.question_name,
            "question_text": self.question_text,
            "system_prompt": self._system_prompt,
            "model": self._model_dict,
        }

        # Include response_model schema if specified
        if self._user_response_model is not None:
            base_data["response_model_schema"] = (
                self._user_response_model.model_json_schema()
            )
            base_data["response_model_name"] = self._user_response_model.__name__

        return base_data

    def to_dict(self, add_edsl_version: bool = True) -> dict:
        """Convert the question to a dictionary for serialization."""
        d = self.data.copy()
        d["question_type"] = self.question_type

        if add_edsl_version:
            from .. import __version__

            d["edsl_version"] = __version__
            d["edsl_class_name"] = "QuestionBase"

        return d

    @classmethod
    def from_dict(cls, data: dict) -> "QuestionInterviewerThinking":
        """
        Create a QuestionInterviewerThinking instance from a dictionary.

        This handles deserialization including recreating a Pydantic model from schema
        if one was specified.
        """
        # Extract the basic fields
        question_name = data.get("question_name")
        question_text = data.get("question_text")
        system_prompt = data.get("system_prompt")
        model_dict = data.get("model")

        # Handle response_model reconstruction
        response_model = None
        if "response_model_schema" in data:
            # Dynamically create a Pydantic model from the schema
            from pydantic import create_model
            from typing import Any as TypingAny

            schema = data["response_model_schema"]
            model_name = data.get("response_model_name", "DynamicResponseModel")

            # Extract fields from the schema
            fields = {}
            properties = schema.get("properties", {})
            required = set(schema.get("required", []))

            for field_name, field_info in properties.items():
                field_type = TypingAny  # Default to Any
                # Try to infer type from schema
                json_type = field_info.get("type")
                if json_type == "string":
                    field_type = str
                elif json_type == "integer":
                    field_type = int
                elif json_type == "number":
                    field_type = float
                elif json_type == "boolean":
                    field_type = bool
                elif json_type == "array":
                    field_type = list
                elif json_type == "object":
                    field_type = dict

                if field_name in required:
                    fields[field_name] = (field_type, ...)
                else:
                    fields[field_name] = (Optional[field_type], None)

            response_model = create_model(model_name, **fields)

        return cls(
            question_name=question_name,
            question_text=question_text,
            model=model_dict,
            system_prompt=system_prompt,
            response_model=response_model,
        )

    @classmethod
    @inject_exception
    def example(cls, randomize: bool = False) -> "QuestionInterviewerThinking":
        """
        Create an example instance of an interviewer thinking question.

        Args:
            randomize: If True, appends a random UUID to ensure uniqueness.

        Returns:
            QuestionInterviewerThinking: An example question instance.

        Examples:
            >>> q = QuestionInterviewerThinking.example()
            >>> q.question_name
            'generate_follow_up'
            >>> 'follow-up' in q.question_text
            True
        """
        from ..language_models import Model

        addition = "" if not randomize else str(uuid4())

        return cls(
            question_name="generate_follow_up",
            question_text=f"The respondent said they enjoy outdoor activities. What's a good follow-up question to learn more about their preferences?{addition}",
            system_prompt="You are a helpful survey researcher. Generate insightful follow-up questions.",
            model=Model("test"),
        )

    def _simulate_answer(self, human_readable: bool = False) -> dict:
        """
        Generate a simulated valid answer for this question.

        Used for testing and examples.
        """
        if self._user_response_model is not None:
            # For structured output, generate a sample based on the schema
            schema = self._user_response_model.model_json_schema()
            sample = {}
            for field_name, field_info in schema.get("properties", {}).items():
                json_type = field_info.get("type", "string")
                if json_type == "string":
                    sample[field_name] = f"Sample {field_name}"
                elif json_type == "integer":
                    sample[field_name] = 42
                elif json_type == "number":
                    sample[field_name] = 3.14
                elif json_type == "boolean":
                    sample[field_name] = True
                elif json_type == "array":
                    sample[field_name] = []
                elif json_type == "object":
                    sample[field_name] = {}
            return {
                "answer": sample,
                "generated_tokens": str(sample),
            }
        else:
            return {
                "answer": "What specific outdoor activities do you enjoy the most?",
                "generated_tokens": "What specific outdoor activities do you enjoy the most?",
            }


def main():
    """Demonstrate the functionality of QuestionInterviewerThinking."""
    # Create an example question
    q = QuestionInterviewerThinking.example()
    print(f"Question name: {q.question_name}")
    print(f"Question text: {q.question_text}")
    print(f"System prompt: {q.system_prompt}")
    print(f"Model: {q.model_dict.get('model')}")

    # Serialize and deserialize
    serialized = q.to_dict()
    print(f"Serialized: {serialized}")

    deserialized = QuestionInterviewerThinking.from_dict(serialized)
    print(
        f"Deserialization successful: {deserialized.question_name == q.question_name}"
    )


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
