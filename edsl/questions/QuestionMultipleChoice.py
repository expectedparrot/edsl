"""This module contains the QuestionMultipleChoice class. It is a subclass of the Question class and is used to create multiple choice questions."""
from __future__ import annotations
from typing import Optional, Union
import random

from jinja2 import Template

from edsl.utilities import random_string
from edsl.questions.descriptors import QuestionOptionsDescriptor
from edsl.questions.Question import Question
from edsl.scenarios import Scenario

class QuestionMultipleChoice(Question):
    """
    This question asks the respondent to select one option from a list of options.

    Arguments:
    :param question_name: The name of the question (string).
    :param question_text: The text of the question (string).
    :param question_options: The options the user should select from (list of strings).

    Optional arguments:
    :param instructions: are the instructions for the question (string). If not provided, the default instructions are used. To view them, run `QuestionCheckBox.default_instructions`.
    :param short_names_dict: maps question_options to short names (dictionary mapping strings to strings).

    For an example, run `QuestionMultipleChoice.example()`.
    """

    question_type = "multiple_choice"
    purpose = "When options are known and limited"
    question_options: list[str] = QuestionOptionsDescriptor()

    def __init__(
        self,
        question_text: str,
        question_options: list[str],
        question_name: str,
        short_names_dict: Optional[dict[str, str]] = None,
    ):
        """Instantiate a new QuestionMultipleChoice."""
        self.question_text = question_text
        self.question_options = question_options
        self.question_name = question_name
        self.short_names_dict = short_names_dict or dict()

    ################
    # Answer methods
    ################
    def validate_answer(
        self, answer: dict[str, Union[str, int]]
    ) -> dict[str, Union[str, int]]:
        """Validate the answer."""
        self.validate_answer_template_basic(answer)
        self.validate_answer_multiple_choice(answer)
        return answer

    def translate_answer_code_to_answer(self, answer_code, scenario: Scenario = None):
        """Translate the answer code to the actual answer."""
        scenario = scenario or Scenario()
        translated_options = [
            Template(str(option)).render(scenario) for option in self.question_options
        ]
        return translated_options[int(answer_code)]

    def simulate_answer(
        self, human_readable: bool = True
    ) -> dict[str, Union[int, str]]:
        """Simulate a valid answer for debugging purposes."""
        if human_readable:
            answer = random.choice(self.question_options)
        else:
            answer = random.choice(range(len(self.question_options)))
        return {
            "answer": answer,
            "comment": random_string(),
        }

    ################
    # Example
    ################
    @classmethod
    def example(cls) -> QuestionMultipleChoice:
        """Return an example instance."""
        return cls(
            question_text="How are you?",
            question_options=["Good", "Great", "OK", "Bad"],
            question_name="how_feeling",
            short_names_dict={"Good": "g", "Great": "gr", "OK": "ok", "Bad": "b"},
        )


def main():
    """Create an example QuestionMultipleChoice and test its methods."""
    from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice

    q = QuestionMultipleChoice.example()
    q.question_text
    q.question_options
    q.question_name
    q.short_names_dict
    # validate an answer
    q.validate_answer({"answer": 0, "comment": "I like custard"})
    # translate answer code
    q.translate_answer_code_to_answer(0, {})
    # simulate answer
    q.simulate_answer()
    q.simulate_answer(human_readable=False)
    # serialization (inherits from Question)
    q.to_dict()
    assert q.from_dict(q.to_dict()) == q
