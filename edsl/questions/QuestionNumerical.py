from __future__ import annotations
import textwrap
from random import uniform
from typing import Any, Optional, Union
from edsl.exceptions import QuestionAnswerValidationError
from edsl.questions import Question
from edsl.questions.descriptors import NumericalOrNoneDescriptor
from edsl.scenarios import Scenario
from edsl.utilities import random_string


class QuestionNumerical(Question):
    """
    This question asks the user to answer with a numerical value.

    Arguments:
    - `question_name` is the name of the question (string)
    - `question_text` is the text of the question (string)

    Optional arguments:
    - `min_value` is the minimum value of the answer (float)
    - `max_value` is the maximum value of the answer (float)
    - `instructions` are the instructions for the question (string). If not provided, the default instructions are used. To view them, run `QuestionNumerical.default_instructions`


    For an example, run `QuestionNumerical.example()`
    """

    question_type = "numerical"
    min_value: Optional[float] = NumericalOrNoneDescriptor()
    max_value: Optional[float] = NumericalOrNoneDescriptor()

    def __init__(
        self,
        question_name: str,
        question_text: str,
        min_value: Optional[Union[int, float]] = None,
        max_value: Optional[Union[int, float]] = None,
    ):
        self.question_name = question_name
        self.question_text = question_text
        self.min_value = min_value
        self.max_value = max_value

    ################
    # Answer methods
    ################
    def validate_answer(
        self, answer: dict[str, Any]
    ) -> dict[str, Union[str, float, int]]:
        """Validates the answer"""
        self.validate_answer_template_basic(answer)
        self.validate_answer_key_value_numeric(answer, "answer")
        self.validate_answer_numerical(answer)
        return answer

    def translate_answer_code_to_answer(self, answer, scenario: Scenario = None):
        """There is no answer code."""
        return answer

    def simulate_answer(self, human_readable: bool = True):
        """Simulates a valid answer for debugging purposes"""
        return {
            "answer": uniform(self.min_value, self.max_value),
            "comment": random_string(),
        }

    ################
    # Helpful methods
    ################
    @classmethod
    def example(cls) -> QuestionNumerical:
        return cls(
            question_name="age",
            question_text="How old are you in years?",
            min_value=0,
            max_value=86.7,
        )


def main():
    from edsl.questions.QuestionNumerical import QuestionNumerical

    q = QuestionNumerical.example()
    q.question_text
    q.min_value
    q.max_value
    # validate an answer
    q.validate_answer({"answer": 1, "comment": "I like custard"})
    # translate answer code
    q.translate_answer_code_to_answer(1)
    # simulate answer
    q.simulate_answer()
    q.simulate_answer(human_readable=False)
    q.validate_answer(q.simulate_answer(human_readable=False))
    # serialization (inherits from Question)
    q.to_dict()
    assert q.from_dict(q.to_dict()) == q
