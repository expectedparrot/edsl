from __future__ import annotations
import random
from typing import Any, Optional, Union

from jinja2 import Template

from edsl.questions.QuestionBase import QuestionBase
from edsl.questions.descriptors import (
    IntegerDescriptor,
    QuestionOptionsDescriptor,
)
from edsl.scenarios import Scenario
from edsl.utilities import random_string


class QuestionMatrix(QuestionBase):
    """This question prompts the agent to select options from a list."""

    question_type = "matrix"
    purpose = "When you have a a matrix of options per items"
    question_options: list[str] = QuestionOptionsDescriptor()
    question_items: list[str] = QuestionOptionsDescriptor()

    def __init__(
        self,
        question_name: str,
        question_text: str,
        question_options: list[str],
        question_items: list[str],
    ):
        self.question_name = question_name
        self.question_text = question_text
        self.question_options = question_options
        self.question_items = question_items

    ################
    # Answer methods
    ################
    def _validate_answer(self, answer: Any) -> dict[str, Union[int, str]]:
        """Validate the answer."""
        self._validate_answer_template_basic(answer)
        self._validate_answer_key_value(answer, "answer", list)
        self._validate_answer_matrix(answer)
        return answer

    def _translate_answer_code_to_answer(self, answer_codes, scenario: Scenario = None):
        """
        Translate the answer code to the actual answer.

        For example, for question options ["a", "b", "c"],the answer codes are 0, 1, and 2.
        The LLM will respond with [0,1] and this code will translate it to ["a","b"].
        """
        scenario = scenario or Scenario()
        translated_options = [
            Template(option).render(scenario) for option in self.question_options
        ]
        translated_codes = []
        for answer_code in answer_codes:
            translated_codes.append(translated_options[int(answer_code)])
        return translated_codes

    def _simulate_answer(self, human_readable=True) -> dict[str, Union[int, str]]:
        """Simulate a valid answer for debugging purposes."""
        if human_readable:
            # Select a random number of options from self.question_options
            selected_options = random.sample(self.question_options, num_selections)
            answer = {
                "answer": selected_options,
                "comment": random_string(),
            }
        else:
            # Select a random number of indices from the range of self.question_options
            selected_indices = random.sample(
                range(len(self.question_options)), num_selections
            )
            answer = {
                "answer": selected_indices,
                "comment": random_string(),
            }
        return answer

    ################
    # Helpful methods
    ################
    @classmethod
    def example(cls) -> QuestionCheckBox:
        """Return an example checkbox question."""
        return cls(
            question_name="never_eat",
            question_text="What is your opinion on these countries?",
            question_items=[
                "Dislike",
                "Neutral",
                "Like",
            ],
            question_options=[
                "France",
                "Spain",
                "Itally",
            ]
        )


def main():
    """Create an example QuestionCheckBox and test its methods."""
    from edsl.questions.QuestionCheckBox import QuestionCheckBox

    q = QuestionMatrix.example()
    q.question_text
    q.question_options
    q.question_items
    q.question_name
    # validate an answer
    q._validate_answer({"answer": [1, 1, 1], "comment": "I'm neutral for these countries"})
    # translate answer code
    q._translate_answer_code_to_answer([1, 1, 1])
    # simulate answer
    q._simulate_answer()
    q._simulate_answer(human_readable=False)
    q._validate_answer(q._simulate_answer(human_readable=False))
    # serialization (inherits from Question)
    q.to_dict()
    assert q.from_dict(q.to_dict()) == q

    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
