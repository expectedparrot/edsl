from __future__ import annotations
import random
import textwrap
from typing import Any, Optional, Union
from edsl.questions.QuestionBase import QuestionBase
from edsl.questions.descriptors import IntegerOrNoneDescriptor

from edsl.scenarios import Scenario
from edsl.utilities import random_string


class QuestionList(QuestionBase):
    """This question prompts the agent to answer by providing a list of items as comma-separated strings."""

    question_type = "list"
    max_list_items: int = IntegerOrNoneDescriptor()

    def __init__(
        self,
        question_name: str,
        question_text: str,
        max_list_items: Optional[int] = None,
    ):
        """Instantiate a new QuestionList.

        :param question_name: The name of the question.
        :param question_text: The text of the question.
        :param instructions: Instructions for the question. If not provided, the default instructions are used. To view them, run `QuestionList.default_instructions`.
        :param max_list_items: The maximum number of items that can be in the answer list.
        """
        self.question_name = question_name
        self.question_text = question_text
        self.max_list_items = max_list_items

    ################
    # Answer methods
    ################
    def _validate_answer(self, answer: Any) -> dict[str, Union[list[str], str]]:
        """Validate the answer."""
        self._validate_answer_template_basic(answer)
        self._validate_answer_key_value(answer, "answer", list)
        self._validate_answer_list(answer)
        return answer

    def _translate_answer_code_to_answer(self, answer, scenario: Scenario = None):
        """There is no answer code."""
        return answer

    def _simulate_answer(self, human_readable: bool = True):
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
            max_list_items=5,
        )


def main():
    """Create an example of a list question and demonstrate its functionality."""
    from edsl.questions.QuestionList import QuestionList

    q = QuestionList.example()
    q.question_text
    q.question_name
    q.max_list_items
    # validate an answer
    q._validate_answer({"answer": ["pasta", "garlic", "oil", "parmesan"]})
    # translate answer code
    q._translate_answer_code_to_answer(["pasta", "garlic", "oil", "parmesan"])
    # simulate answer
    q._simulate_answer()
    q._simulate_answer(human_readable=False)
    q._validate_answer(q._simulate_answer(human_readable=False))
    # serialization (inherits from Question)
    q.to_dict()
    assert q.from_dict(q.to_dict()) == q

    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
