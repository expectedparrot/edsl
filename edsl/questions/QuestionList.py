from __future__ import annotations
import random
import textwrap
from typing import Any, Optional, Union
from edsl.questions import Question
from edsl.questions.descriptors import (
    QuestionAllowNonresponseDescriptor,
    IntegerOrNoneDescriptor,
)
from edsl.scenarios import Scenario
from edsl.utilities import random_string


class QuestionList(Question):
    """
    QuestionList is a question where the user is asked to provide a list of comma-separated words or phrases.
    - `question_text` is the question text
    - `allow_nonresponse` is a boolean indicating whether the user can skip the question
    - `max_list_items` is an integer indicating the maximum number of items in the list

    For an example, run `QuestionList.example()`
    """

    question_type = "list"
    max_list_items: Optional[int] = IntegerOrNoneDescriptor()
    allow_nonresponse: bool = QuestionAllowNonresponseDescriptor()
    default_instructions = textwrap.dedent(
        """\
        {{question_text}}

        Your response should be only a valid JSON of the following format:
        {
            "answer": <list of comma-separated words or phrases >, 
            "comment": "<put comment here>"
        }
        {% if max_list_items is not none %}
        The list must not contain more than {{ max_list_items }} items.
        {% endif %}                                           
    """
    )

    def __init__(
        self,
        question_text: str,
        question_name: str,
        allow_nonresponse: Optional[bool] = None,
        short_names_dict: Optional[dict[str, str]] = None,
        instructions: Optional[str] = None,
        max_list_items: Optional[int] = None,
    ):
        self.question_text = question_text
        self.question_name = question_name
        self.instructions = instructions or self.default_instructions
        self.allow_nonresponse = allow_nonresponse or False
        self.max_list_items = max_list_items
        self.short_names_dict = short_names_dict or dict()

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
    q.instructions
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
