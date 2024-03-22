"""This module contains the QuestionList class. It is a subclass of the Question class and is used to create questions where the desired response is in the form of a list.
Example usage:

.. code-block:: python

    from edsl.questions import QuestionList

    q = QuestionList(
        question_name = "work_days",
        question_text = "Which days of the week do you normally work?"
    )

"""
from __future__ import annotations
import random
import textwrap
from typing import Any, Optional, Union
from edsl.questions import Question
from edsl.questions.descriptors import (
    AllowNonresponseDescriptor,
    IntegerOrNoneDescriptor,
)
from edsl.scenarios import Scenario
from edsl.utilities import random_string


class QuestionList(Question):
    """
    This question asks the respondent to answer by providing a list of items as comma-separated strings.

    :param question_name: The name of the question.
    :type question_name: str
    :param question_text: The text of the question.
    :type question_text: str
    :param instructions: Instructions for the question. If not provided, the default instructions are used. To view them, run `QuestionList.default_instructions`.
    :type instructions: str, optional
    :param max_list_items: The maximum number of items that can be in the answer list.
    :type max_list_items: int, optional

    For an example, run `QuestionList.example()`.
    """

    question_type = "list"
    max_list_items: int = IntegerOrNoneDescriptor()
    allow_nonresponse: bool = AllowNonresponseDescriptor()

    def __init__(
        self,
        question_text: str,
        question_name: str,
        allow_nonresponse: Optional[bool] = None,
        max_list_items: Optional[int] = None,
    ):
        """Instantiate a new QuestionList."""
        self.question_text = question_text
        self.question_name = question_name
        self.allow_nonresponse = allow_nonresponse or False
        self.max_list_items = max_list_items

    ################
    # Answer methods
    ################
    def validate_answer(self, answer: Any) -> dict[str, Union[list[str], str]]:
        """Validate the answer."""
        self.validate_answer_template_basic(answer)
        self.validate_answer_key_value(answer, "answer", list)
        self.validate_answer_list(answer)
        return answer

    def translate_answer_code_to_answer(self, answer, scenario: Scenario = None):
        """There is no answer code."""
        return answer

    def simulate_answer(self, human_readable: bool = True):
        """Simulate a valid answer for debugging purposes (what the validator expects)."""
        num_items = random.randint(1, self.max_list_items or 2)
        return {"answer": [random_string() for _ in range(num_items)]}

    ################
    # Helpful methods
    ################
    @classmethod
    def example(cls) -> QuestionList:
        """Return an example of a list question."""
        return cls(
            question_name="list_of_foods",
            question_text="What are your favorite foods?",
            allow_nonresponse=False,
            max_list_items=5,
        )


def main():
    """Create an example of a list question and demonstrate its functionality."""
    from edsl.questions.QuestionList import QuestionList

    q = QuestionList.example()
    q.question_text
    q.question_name
    q.allow_nonresponse
    q.max_list_items
    # validate an answer
    q.validate_answer({"answer": ["pasta", "garlic", "oil", "parmesan"]})
    # translate answer code
    q.translate_answer_code_to_answer(["pasta", "garlic", "oil", "parmesan"])
    # simulate answer
    q.simulate_answer()
    q.simulate_answer(human_readable=False)
    q.validate_answer(q.simulate_answer(human_readable=False))
    # serialization (inherits from Question)
    q.to_dict()
    assert q.from_dict(q.to_dict()) == q
