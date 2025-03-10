from __future__ import annotations
from typing import Any, Optional
from typing import Optional, Any, List

from uuid import uuid4

from pydantic import field_validator, model_validator, BaseModel

from ..prompts import Prompt

from .exceptions import QuestionAnswerValidationError
from .question_base import QuestionBase
from .response_validator_abc import ResponseValidatorABC
from .decorators import inject_exception


class FreeTextResponse(BaseModel):
    """
    Validator for free text response questions.
    """

    answer: str
    generated_tokens: Optional[str] = None

    @model_validator(mode='after')
    def validate_tokens_match_answer(self):
        if self.generated_tokens is not None:  # If generated_tokens exists
            # Ensure exact string equality
            if self.answer.strip() != self.generated_tokens.strip():  # They MUST match exactly
                raise ValueError(
                    f"answer '{self.answer}' must exactly match generated_tokens '{self.generated_tokens}'. "
                    f"Type of answer: {type(self.answer)}, Type of tokens: {type(self.generated_tokens)}"
                )
        return self


class FreeTextResponseValidator(ResponseValidatorABC):
    required_params = []
    valid_examples = [({"answer": "This is great"}, {})]
    invalid_examples = [
        (
            {"answer": None},
            {},
            "Answer code must not be missing.",
        ),
    ]

    def fix(self, response, verbose=False):
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
    """This question prompts the agent to respond with free text."""

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
        """Instantiate a new QuestionFreeText.

        :param question_name: The name of the question.
        :param question_text: The text of the question.
        """
        self.question_name = question_name
        self.question_text = question_text
        self.answering_instructions = answering_instructions
        self.question_presentation = question_presentation

    @property
    def question_html_content(self) -> str:
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
    def example(cls, randomize: bool = False) -> QuestionFreeText:
        """Return an example instance of a free text question."""
        addition = "" if not randomize else str(uuid4())
        return cls(question_name="how_are_you", question_text=f"How are you?{addition}")


def main():
    """Create an example question and demonstrate its functionality."""
    from .question_free_text import QuestionFreeText

    q = QuestionFreeText.example()
    q.question_text
    q.question_name
    # q.instructions
    # validate an answer
    q._validate_answer({"answer": "I like custard"})
    # translate answer code
    q._translate_answer_code_to_answer({"answer"})
    # simulate answer
    q._simulate_answer()
    q._simulate_answer(human_readable=False)
    q._validate_answer(q._simulate_answer(human_readable=False))
    # serialization (inherits from Question)
    q.to_dict()
    assert q.from_dict(q.to_dict()) == q

    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
