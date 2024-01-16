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
    This question asks the user to answer by providing a list of items as comma-separated strings.

    Arguments:
    - `question_name` is the name of the question (string)
    - `question_text` is the text of the question (string)

    Optional arguments:
    - `max_list_items` is the maximum number of items that can be in the answer list (positive integer)
    - `allow_nonresponse` is whether the user can skip the question (boolean). If not provided, the default is False.
    - `instructions` are the instructions for the question (string). If not provided, the default instructions are used. To view them, run `QuestionList.default_instructions`

    For an example, run `QuestionList.example()`
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
        self.question_text = question_text
        self.question_name = question_name
        self.allow_nonresponse = allow_nonresponse or False
        self.max_list_items = max_list_items

    ################
    # Answer methods
    ################
    def validate_answer(self, answer: Any) -> dict[str, Union[list[str], str]]:
        """Validates the answer"""
        self.validate_answer_template_basic(answer)
        self.validate_answer_key_value(answer, "answer", list)
        self.validate_answer_list(answer)
        return answer

    def translate_answer_code_to_answer(self, answer, scenario: Scenario = None):
        """There is no answer code."""
        return answer

    def simulate_answer(self, human_readable: bool = True):
        "Simulates a valid answer for debugging purposes (what the validator expects)"
        num_items = random.randint(1, self.max_list_items or 2)
        return {"answer": [random_string() for _ in range(num_items)]}

    ################
    # Helpful methods
    ################
    @classmethod
    def example(cls) -> QuestionList:
        return cls(
            question_name="list_of_foods",
            question_text="What are your favorite foods?",
            allow_nonresponse=False,
            max_list_items=5,
        )


def main():
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
