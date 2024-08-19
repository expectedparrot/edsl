from __future__ import annotations
import textwrap
from typing import Any, Optional
from uuid import uuid4
from edsl.questions.QuestionBase import QuestionBase


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

    def __init__(self, question_name: str, question_text: str):
        """Instantiate a new QuestionFreeText.

        :param question_name: The name of the question.
        :param question_text: The text of the question.
        """
        self.question_name = question_name
        self.question_text = question_text

    ################
    # Answer methods
    ################
    def _validate_answer(self, answer: Any) -> dict[str, str]:
        """Validate the answer."""
        self._validate_answer_template_basic(answer)
        self._validate_answer_key_value(answer, "answer", str)
        return answer

    def _translate_answer_code_to_answer(self, answer, scenario: "Scenario" = None):
        """Do nothing, because the answer is already in a human-readable format."""
        return answer

    def _simulate_answer(self, human_readable: bool = True) -> dict[str, str]:
        """Simulate a valid answer for debugging purposes."""
        from edsl.utilities.utilities import random_string

        return {"answer": random_string()}

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
    def example(cls, randomize: bool = False) -> QuestionFreeText:
        """Return an example instance of a free text question."""
        addition = "" if not randomize else str(uuid4())
        return cls(question_name="how_are_you", question_text=f"How are you?{addition}")


def main():
    """Create an example question and demonstrate its functionality."""
    from edsl.questions.QuestionFreeText import QuestionFreeText

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
