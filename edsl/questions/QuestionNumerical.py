from __future__ import annotations
import textwrap
from random import uniform
from typing import Any, Optional, Union
from edsl.exceptions import QuestionAnswerValidationError
from edsl.questions.QuestionBase import QuestionBase
from edsl.questions.descriptors import NumericalOrNoneDescriptor
from edsl.scenarios import Scenario
from edsl.utilities import random_string


class QuestionNumerical(QuestionBase):
    """This question prompts the agent to answer with a numerical value."""

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
        """Initialize the question.

        :param question_name: The name of the question.
        :param question_text: The text of the question.
        :param instructions: Instructions for the question. If not provided, the default instructions are used. To view them, run `QuestionNumerical.default_instructions`.
        :param min_value: The minimum value of the answer.
        :param max_value: The maximum value of the answer.
        """
        self.question_name = question_name
        self.question_text = question_text
        self.min_value = min_value
        self.max_value = max_value

    ################
    # Answer methods
    ################
    def _validate_answer(
        self, answer: dict[str, Any]
    ) -> dict[str, Union[str, float, int]]:
        """Validate the answer."""
        self._validate_answer_template_basic(answer)
        self._validate_answer_key_value_numeric(answer, "answer")
        self._validate_answer_numerical(answer)
        return answer

    def _translate_answer_code_to_answer(self, answer, scenario: Scenario = None):
        """There is no answer code."""
        return answer

    def _simulate_answer(self, human_readable: bool = True):
        """Simulate a valid answer for debugging purposes."""
        return {
            "answer": uniform(self.min_value, self.max_value),
            "comment": random_string(),
        }

    ################
    # Helpful methods
    ################
    @classmethod
    def example(cls) -> QuestionNumerical:
        """Return an example question."""
        return cls(
            question_name="age",
            question_text="How old are you in years?",
            min_value=0,
            max_value=86.7,
        )


def main():
    """Show example usage."""
    from edsl.questions.QuestionNumerical import QuestionNumerical

    q = QuestionNumerical.example()
    q.question_text
    q.min_value
    q.max_value
    # validate an answer
    q._validate_answer({"answer": 1, "comment": "I like custard"})
    # translate answer code
    q._translate_answer_code_to_answer(1)
    # simulate answer
    q._simulate_answer()
    q._simulate_answer(human_readable=False)
    q._validate_answer(q._simulate_answer(human_readable=False))
    # serialization (inherits from Question)
    q.to_dict()
    assert q.from_dict(q.to_dict()) == q

    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
