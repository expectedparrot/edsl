from __future__ import annotations
import textwrap
from typing import Any, Optional
from edsl.questions import Question
from edsl.questions.descriptors import AllowNonresponseDescriptor
from edsl.scenarios import Scenario
from edsl.utilities import random_string


# TODO: should allow answer = {"answer": None} if allow_nonresponse is True
class QuestionFreeText(Question):
    """
    This question asks the user to answer with free text.

    Arguments:
    - `question_name` is the name of the question (string)
    - `question_text` is the text of the question (string)

    Optional arguments:
    - `allow_nonresponse` is whether the user can skip the question (boolean). If not provided, the default is False.
    - `instructions` are the instructions for the question (string). If not provided, the default instructions are used. To view them, run `QuestionFreeText.default_instructions`

    For an example, run `QuestionFreeText.example()`
    """

    question_type = "free_text"
    allow_nonresponse: bool = AllowNonresponseDescriptor()
    default_instructions = textwrap.dedent(
        """\
        You are being asked the following question: {{question_text}}
        Return a valid JSON formatted like this: 
        {"answer": "<put free text answer here>"}
        """
    )

    def __init__(
        self,
        question_text: str,
        question_name: str,
        allow_nonresponse: Optional[bool] = None,
        instructions: Optional[str] = None,
    ):
        self.question_text = question_text
        self.question_name = question_name
        self.allow_nonresponse = allow_nonresponse or False
        self.instructions = instructions

    ################
    # Answer methods
    ################
    def validate_answer(self, answer: Any) -> dict[str, str]:
        self.validate_answer_template_basic(answer)
        self.validate_answer_key_value(answer, "answer", str)
        return answer

    def translate_answer_code_to_answer(self, answer, scenario: Scenario = None):
        """Does nothing, because the answer is already in a human-readable format."""
        return answer

    def simulate_answer(self, human_readable: bool = True) -> dict[str, str]:
        return {"answer": random_string()}

    @classmethod
    def example(cls) -> QuestionFreeText:
        return cls(
            question_name="how_are_you",
            question_text="How are you?",
            allow_nonresponse=True,
        )


def main():
    from edsl.questions.QuestionFreeText import QuestionFreeText

    q = QuestionFreeText.example()
    q.question_text
    q.question_name
    q.instructions
    # validate an answer
    q.validate_answer({"answer": "I like custard"})
    # translate answer code
    q.translate_answer_code_to_answer({"answer"})
    # simulate answer
    q.simulate_answer()
    q.simulate_answer(human_readable=False)
    q.validate_answer(q.simulate_answer(human_readable=False))
    # serialization (inherits from Question)
    q.to_dict()
    assert q.from_dict(q.to_dict()) == q
