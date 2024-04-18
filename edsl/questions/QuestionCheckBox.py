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


class QuestionCheckBox(QuestionBase):
    """This question prompts the agent to select options from a list."""

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
    ):
        """Instantiate a new QuestionCheckBox.

        :param question_name: The name of the question.
        :param question_text: The text of the question.
        :param question_options: The options the respondent should select from.
        :param instructions: Instructions for the question. If not provided, the default instructions are used. To view them, run `QuestionCheckBox.default_instructions`.
        :param min_selections: The minimum number of options that must be selected.
        :param max_selections: The maximum number of options that must be selected.
        """
        self.question_name = question_name
        self.question_text = question_text
        self.min_selections = min_selections
        self.max_selections = max_selections
        self.question_options = question_options

    ################
    # Answer methods
    ################
    def _validate_answer(self, answer: Any) -> dict[str, Union[int, str]]:
        """Validate the answer."""
        self._validate_answer_template_basic(answer)
        self._validate_answer_key_value(answer, "answer", list)
        self._validate_answer_checkbox(answer)
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
    # validate an answer
    q._validate_answer({"answer": [1, 2], "comment": "I like custard"})
    # translate answer code
    q._translate_answer_code_to_answer([1, 2])
    # simulate answer
    q._simulate_answer()
    q._simulate_answer(human_readable=False)
    q._validate_answer(q._simulate_answer(human_readable=False))
    # serialization (inherits from Question)
    q.to_dict()
    assert q.from_dict(q.to_dict()) == q

    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
