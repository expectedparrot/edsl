"""This module contains the QuestionCheckBox class. It is a subclass of the Question class and is used to create questions where the respondent is prompted to select one or more of the given options and return them as a list.
The minimum and maximum number of options that can be selected can be specified when creating the question. If not specified, the minimum is 1 and the maximum is the number of options in the question.
Example usage:
```
from edsl.questions import QuestionCheckBox

q = QuestionCheckBox(
    question_name = "favorite_days",
    question_text = "What are your 2 favorite days of the week?",
    question_options = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
    min_selections = 2,
    max_selections = 2
)
```
See more details about constructing and administering questions in the <a href="https://docs.expectedparrot.com/en/latest/scenarios.html">`Question`</a> module.
"""
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
    This question asks the respondent to select options from a list.

    :param question_name: The name of the question.
    :type question_name: str
    :param question_text: The text of the question.
    :type question_text: str
    :param question_options: The options the respondent should select from.
    :type question_options: list[str]
    :param instructions: Instructions for the question. If not provided, the default instructions are used. To view them, run `QuestionCheckBox.default_instructions`.
    :type instructions: str, optional
    :param short_names_dict: Maps question_options to short names.
    :type short_names_dict: dict[str, str], optional
    :param min_selections: The minimum number of options that must be selected.
    :type min_selections: int, optional
    :param max_selections: The maximum number of options that must be selected.
    :type max_selections: int, optional
    
    For an example, run `QuestionCheckBox.example()`.
    """

    question_type = "checkbox"
    purpose = "When options are known and limited"
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
        """Instantiate a new QuestionCheckBox."""
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
        """Validate the answer."""
        self.validate_answer_template_basic(answer)
        self.validate_answer_key_value(answer, "answer", list)
        self.validate_answer_checkbox(answer)
        return answer

    def translate_answer_code_to_answer(self, answer_codes, scenario: Scenario = None):
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

    def simulate_answer(self, human_readable=True) -> dict[str, Union[int, str]]:
        """Simulate a valid answer for debugging purposes."""
        min_selections = self.min_selections or 1
        max_selections = self.max_selections or len(self.question_options)
        num_selections = random.randint(min_selections, max_selections)
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
    """Create an example QuestionCheckBox and test its methods."""
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
