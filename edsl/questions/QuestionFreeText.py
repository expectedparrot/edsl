from __future__ import annotations
import textwrap
from typing import Any, Optional
from edsl.questions.QuestionBase import QuestionBase
from edsl.scenarios import Scenario
from edsl.utilities import random_string


class QuestionFreeText(QuestionBase):
    """This question prompts the agent to respond with free text."""

    question_type = "free_text"
    default_instructions = textwrap.dedent(
        """\
        You are being asked the following question: {{question_text}}
        Return a valid JSON formatted like this: 
        {"answer": "<put free text answer here>"}
        """
    )

    def __init__(
        self,
        question_name: str,
        question_text: str,
        instructions: Optional[str] = None,
    ):
        """Instantiate a new QuestionFreeText.

        :param question_name: The name of the question.
        :param question_text: The text of the question.
        :param instructions: Instructions for the question. If not provided, the default instructions are used. To view them, run `QuestionFreeText.default_instructions`.
        """
        self.question_name = question_name
        self.question_text = question_text
        self.instructions = instructions

    ################
    # Answer methods
    ################
    def _validate_answer(self, answer: Any) -> dict[str, str]:
        """Validate the answer."""
        self._validate_answer_template_basic(answer)
        self._validate_answer_key_value(answer, "answer", str)
        return answer

    def _translate_answer_code_to_answer(self, answer, scenario: Scenario = None):
        """Do nothing, because the answer is already in a human-readable format."""
        return answer

    def _simulate_answer(self, human_readable: bool = True) -> dict[str, str]:
        """Simulate a valid answer for debugging purposes."""
        return {"answer": random_string()}

    @classmethod
    def example(cls) -> QuestionFreeText:
        """Return an example instance of a free text question."""
        return cls(question_name="how_are_you", question_text="How are you?")


def main():
    """Create an example question and demonstrate its functionality."""
    from edsl.questions.QuestionFreeText import QuestionFreeText

    q = QuestionFreeText.example()
    q.question_text
    q.question_name
    q.instructions
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
