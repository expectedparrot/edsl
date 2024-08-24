from __future__ import annotations
import random
import textwrap
from typing import Any, Optional, Union
from edsl.questions.QuestionBase import QuestionBase
from edsl.questions.descriptors import IntegerOrNoneDescriptor
from edsl.questions.decorators import inject_exception

from pydantic import field_validator
from edsl.questions.ResponseValidatorABC import ResponseValidatorABC
from edsl.questions.ResponseValidatorABC import BaseResponse

from edsl.exceptions import QuestionAnswerValidationError
import textwrap


class ListResponse(BaseResponse):
    """
    >>> nr = ListResponse(answer = ["Apple", "Cherry"])
    >>> nr.dict()
    {'answer': ['Apple', 'Cherry'], 'comment': None}
    """

    answer: list[Union[str, int, float, list, dict]]


class ListResponseValidator(ResponseValidatorABC):

    required_params = ["max_list_items"]
    valid_examples = [({"answer": ["hello", "world"]}, {"max_list_items": 5})]

    invalid_examples = [
        (
            {"answer": ["hello", "world", "this", "is", "a", "test"]},
            {"max_list_items": 5},
            "Too many items.",
        ),
    ]

    def custom_validate(self, response) -> ListResponse:
        if (
            self.max_list_items is not None
            and len(response.answer) > self.max_list_items
        ):
            raise QuestionAnswerValidationError("Too many items.")
        return response.dict()


class QuestionList(QuestionBase):
    """This question prompts the agent to answer by providing a list of items as comma-separated strings."""

    question_type = "list"
    max_list_items: int = IntegerOrNoneDescriptor()
    _response_model = ListResponse
    response_validator_class = ListResponseValidator

    def __init__(
        self,
        question_name: str,
        question_text: str,
        max_list_items: Optional[int] = None,
        include_comment: bool = True,
        answering_instructions: Optional[str] = None,
        question_presentation: Optional[str] = None,
    ):
        """Instantiate a new QuestionList.

        :param question_name: The name of the question.
        :param question_text: The text of the question.
        :param max_list_items: The maximum number of items that can be in the answer list.

        >>> QuestionList.example().self_check()
        """
        self.question_name = question_name
        self.question_text = question_text
        self.max_list_items = max_list_items

        self.include_comment = include_comment
        self.answering_instructions = answering_instructions
        self.question_presentations = question_presentation

    @property
    def question_html_content(self) -> str:
        from jinja2 import Template

        question_html_content = Template(
            """
        <div id="question-list-container">
            <div>
                <textarea name="{{ question_name }}[]" rows="1" placeholder="Enter item"></textarea>
            </div>
        </div>
        <button type="button" onclick="addNewLine()">Add another line</button>

        <script>
            function addNewLine() {
                var container = document.getElementById('question-list-container');
                var newLine = document.createElement('div');
                newLine.innerHTML = '<textarea name="{{ question_name }}[]" rows="1" placeholder="Enter item"></textarea>';
                container.appendChild(newLine);
            }
        </script>
        """
        ).render(question_name=self.question_name)
        return question_html_content

    ################
    # Helpful methods
    ################
    @classmethod
    @inject_exception
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


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
