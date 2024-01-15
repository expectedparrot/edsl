from __future__ import annotations
import random
import textwrap
from jinja2 import Template
from typing import Any, Optional, Union
from edsl.questions import Question
from edsl.questions.descriptors import (
    IntegerDescriptor,
    QuestionOptionsDescriptor,
)
from edsl.scenarios import Scenario
from edsl.utilities import random_string


class QuestionCheckBox(Question):
    """
    This question asks the user to select options from a list.

    Arguments:
    - `question_name` is the name of the question (string)
    - `question_options` are the options the user should select from (list of strings)
    - `question_text` is the text of the question (string)

    Optional arguments:
    - `min_selections` is the minimum number of options that must be selected (positive integer)
    - `max_selections` is the maximum number of options that must be selected (positive integer)
    - `instructions` are the instructions for the question (string). If not provided, the default instructions are used. To view them, run `QuestionCheckBox.default_instructions`
    - `short_names_dict` maps question_options to short names (dictionary mapping strings to strings)

    For an example, run `QuestionCheckBox.example()`
    """

    question_type = "checkbox"
    question_options: list[str] = QuestionOptionsDescriptor()
    min_selections = IntegerDescriptor(none_allowed=True)
    max_selections = IntegerDescriptor(none_allowed=True)

    def __init__(
        self,
        question_name: str,
        question_text: str,
        question_options: list[str],
        min_selections: Optional[int] = None,
        max_selections: Optional[int] = None,
        short_names_dict: Optional[dict[str, str]] = None,
    ):
        self.question_name = question_name
        self.question_text = question_text
        self.min_selections = min_selections
        self.max_selections = max_selections
        self.question_options = question_options
        self.short_names_dict = short_names_dict or dict()

    ################
    # Answer methods
    ################
    def validate_answer(self, answer: Any) -> dict[str, Union[int, str]]:
        self.validate_answer_template_basic(answer)
        self.validate_answer_key_value(answer, "answer", list)
        self.validate_answer_checkbox(answer)
        return answer

    def translate_answer_code_to_answer(self, answer_codes, scenario: Scenario = None):
        """
        Translates the answer code to the actual answer.
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

    def simulate_answer(self, human_readable=True) -> dict[str, Union[int, str]]:
        """Simulates a valid answer for debugging purposes"""
        num_selections = random.randint(self.min_selections, self.max_selections)
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
        return cls(
            question_name="never_eat",
            question_text="Which of the following foods would you eat if you had to?",
            question_options=[
                "soggy meatpie",
                "rare snails",
                "mouldy bread",
                "panda milk custard",
                "McDonalds",
            ],
            min_selections=2,
            max_selections=5,
        )


def main():
    from edsl.questions.QuestionCheckBox import QuestionCheckBox

    q = QuestionCheckBox.example()
    q.question_text
    q.question_options
    q.question_name
    q.short_names_dict
    # validate an answer
    q.validate_answer({"answer": [1, 2], "comment": "I like custard"})
    # translate answer code
    q.translate_answer_code_to_answer([1, 2])
    # simulate answer
    q.simulate_answer()
    q.simulate_answer(human_readable=False)
    q.validate_answer(q.simulate_answer(human_readable=False))
    # serialization (inherits from Question)
    q.to_dict()
    assert q.from_dict(q.to_dict()) == q
