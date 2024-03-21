"""This module contains the QuestionRank class."""
from __future__ import annotations
import random
import textwrap
from jinja2 import Template
from typing import Any, Optional, Union
from edsl.questions import Question
from edsl.exceptions import QuestionAnswerValidationError
from edsl.scenarios import Scenario
from edsl.utilities.utilities import random_string
from edsl.questions.descriptors import (
    QuestionOptionsDescriptor,
    NumSelectionsDescriptor,
)


class QuestionRank(Question):
    """
    This question asks the respondent to rank options from a list.

    :param question_name: The name of the question.
    :type question_name: str
    :param question_text: The text of the question.
    :type question_text: str
    :param question_options: The options the respondent should select from.
    :type question_options: list[str]
    :param instructions: Instructions for the question. If not provided, the default instructions are used. To view them, run `QuestionRank.default_instructions`.
    :type instructions: str, optional
    :param short_names_dict: Maps question_options to short names.
    :type short_names_dict: dict[str, str], optional
    :param num_selections: The number of options that must be selected.
    :type num_selections: int, optional

    For an example, run `QuestionRank.example()`.
    """

    question_type = "rank"
    question_options: list[str] = QuestionOptionsDescriptor()
    num_selections = NumSelectionsDescriptor()

    def __init__(
        self,
        question_name: str,
        question_text: str,
        question_options: list[str],
        num_selections: Optional[int] = None,
        short_names_dict: Optional[dict[str, str]] = None,
    ):
        """Initialize the question."""
        self.question_name = question_name
        self.question_text = question_text
        self.question_options = question_options
        self.short_names_dict = short_names_dict or dict()
        self.num_selections = num_selections or len(question_options)

    ################
    # Answer methods
    ################
    def validate_answer(self, answer: Any) -> dict[str, list[int]]:
        """Validate the answer."""
        self.validate_answer_template_basic(answer)
        self.validate_answer_key_value(answer, "answer", list)
        self.validate_answer_rank(answer)
        return answer

    def translate_answer_code_to_answer(
        self, answer_codes, scenario: Scenario = None
    ) -> list[str]:
        """Translate the answer code to the actual answer."""
        scenario = scenario or Scenario()
        translated_options = [
            Template(option).render(scenario) for option in self.question_options
        ]
        translated_codes = []
        for answer_code in answer_codes:
            translated_codes.append(translated_options[int(answer_code)])
        return translated_codes

    def simulate_answer(self, human_readable=True) -> dict[str, Union[int, str]]:
        """Simulate a valid answer for debugging purposes."""
        if human_readable:
            selected = random.sample(self.question_options, self.num_selections)
        else:
            selected = random.sample(
                range(len(self.question_options)), self.num_selections
            )
        answer = {
            "answer": selected,
            "comment": random_string(),
        }
        return answer

    ################
    # Helpful methods
    ################
    @classmethod
    def example(cls) -> QuestionRank:
        """Return an example question."""
        return cls(
            question_name="rank_foods",
            question_text="Rank your favorite foods.",
            question_options=["Pizza", "Pasta", "Salad", "Soup"],
            num_selections=2,
        )


def main():
    """Show example usage."""
    from edsl.questions.QuestionRank import QuestionRank

    q = QuestionRank.example()
    q.question_text
    q.question_name
    q.question_options
    q.num_selections
    # validate an answer
    answer = {"answer": [0, 1], "comment": "I like pizza and pasta."}
    q.validate_answer(answer)
    # translate an answer code to an answer
    q.translate_answer_code_to_answer([0, 1])
    # simulate answer
    q.simulate_answer()
    q.simulate_answer(human_readable=False)
    q.validate_answer(q.simulate_answer(human_readable=False))
    # serialization (inherits from Question)
    q.to_dict()
    assert q.from_dict(q.to_dict()) == q
