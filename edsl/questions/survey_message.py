"""A routable survey message that requires no respondent or model answer."""

from html import escape
from typing import Literal, Optional

from pydantic import BaseModel

from .question_base import QuestionBase
from .response_validator_abc import ResponseValidatorABC


class SurveyMessageResponse(BaseModel):
    """The deterministic response recorded after displaying a survey message."""

    answer: Literal["continued"]
    comment: Optional[str] = None
    generated_tokens: Optional[str] = None


class SurveyMessageResponseValidator(ResponseValidatorABC):
    """Validate the deterministic response produced by SurveyMessage."""

    required_params = []
    valid_examples = [({"answer": "continued"}, {})]
    invalid_examples = [
        ({"answer": "anything else"}, {}, "Input should be 'continued'")
    ]

    def fix(self, response, verbose=False):
        """Messages are deterministic and do not repair arbitrary responses."""
        return response


class SurveyMessage(QuestionBase):
    """Display-only, routable content in a survey sequence.

    Unlike an Instruction, which supplies context to subsequent questions, a
    SurveyMessage is an ordinary integer-indexed survey node. Rules may target
    it by name, and execution records the deterministic answer "continued"
    without invoking a language model.
    """

    question_type = "survey_message"
    _response_model = SurveyMessageResponse
    response_validator_class = SurveyMessageResponseValidator

    def __init__(
        self,
        question_name: str,
        question_text: str,
        question_presentation: Optional[str] = None,
        answering_instructions: Optional[str] = None,
    ):
        self.question_name = question_name
        self.question_text = question_text

    def answer_question_directly(self, scenario=None, agent_traits=None) -> dict:
        """Return the deterministic continuation response without inference."""
        return {
            "answer": "continued",
            "comment": "Automatically continued past a survey message.",
            "generated_tokens": "continued",
        }

    def _translate_answer_code_to_answer(self, answer, replacements_dict=None):
        """Return the already human-readable deterministic answer."""
        return answer

    def _simulate_answer(self, human_readable: bool = False) -> dict:
        """Return the deterministic response used by simulations."""
        return self.answer_question_directly()

    @property
    def question_html_content(self) -> str:
        """Return simple display markup; interactive clients provide the action."""
        return f'<div class="survey-message">{escape(self.question_text)}</div>'
