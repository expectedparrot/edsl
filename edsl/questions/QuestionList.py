from __future__ import annotations
import random
import textwrap
from typing import Any, Optional, Union
from edsl.questions.QuestionBase import QuestionBase
from edsl.questions.descriptors import IntegerOrNoneDescriptor
from edsl.questions.decorators import inject_exception

from pydantic import field_validator, Field
from edsl.questions.ResponseValidatorABC import ResponseValidatorABC
from edsl.questions.ResponseValidatorABC import BaseResponse

from edsl.exceptions import QuestionAnswerValidationError
import textwrap
import json

from json_repair import repair_json


def convert_string(s):
    """Convert a string to a more appropriate type if possible.

    >>> convert_string("3.14")
    3.14
    >>> convert_string("42")
    42
    >>> convert_string("hello")
    'hello'
    >>> convert_string('{"key": "value"}')
    {'key': 'value'}
    >>> convert_string("{'key': 'value'}")
    {'key': 'value'}
    """

    if not isinstance(s, str):  # if it's not a string, return it as is
        return s

    # If the repair returns, continue on; otherwise, try to load it as JSON
    if (repaired_json := repair_json(s)) == '""':
        pass
    else:
        try:
            return json.loads(repaired_json)
        except json.JSONDecodeError:
            pass

    # Try to convert to float
    try:
        return float(s)
    except ValueError:
        pass

    # Try to convert to int
    try:
        return int(s)
    except ValueError:
        pass

    # If all conversions fail, return the original string
    return s


def create_model(max_list_items: int, permissive):
    from pydantic import BaseModel

    if permissive or max_list_items is None:

        class ListResponse(BaseModel):
            answer: list[Any]
            comment: Optional[str] = None
            generated_tokens: Optional[str] = None

    else:

        class ListResponse(BaseModel):
            """
            >>> nr = ListResponse(answer=["Apple", "Cherry"])
            >>> nr.dict()
            {'answer': ['Apple', 'Cherry'], 'comment': None, 'generated_tokens': None}
            """

            answer: list[Any] = Field(..., min_items=0, max_items=max_list_items)
            comment: Optional[str] = None
            generated_tokens: Optional[str] = None

    return ListResponse


class ListResponseValidator(ResponseValidatorABC):
    required_params = ["max_list_items", "permissive"]
    valid_examples = [({"answer": ["hello", "world"]}, {"max_list_items": 5})]

    invalid_examples = [
        (
            {"answer": ["hello", "world", "this", "is", "a", "test"]},
            {"max_list_items": 5},
            "Too many items.",
        ),
    ]

    def _check_constraints(self, response) -> None:
        if (
            self.max_list_items is not None
            and len(response.answer) > self.max_list_items
        ):
            raise QuestionAnswerValidationError("Too many items.")

    def fix(self, response, verbose=False):
        if verbose:
            print(f"Fixing list response: {response}")
        answer = str(response.get("answer") or response.get("generated_tokens", ""))
        if len(answer.split(",")) > 0:
            return (
                {"answer": answer.split(",")} | {"comment": response.get("comment")}
                if "comment" in response
                else {}
            )

    def _post_process(self, edsl_answer_dict):
        edsl_answer_dict["answer"] = [
            convert_string(item) for item in edsl_answer_dict["answer"]
        ]
        return edsl_answer_dict


class QuestionList(QuestionBase):
    """This question prompts the agent to answer by providing a list of items as comma-separated strings."""

    question_type = "list"
    max_list_items: int = IntegerOrNoneDescriptor()
    _response_model = None
    response_validator_class = ListResponseValidator

    def __init__(
        self,
        question_name: str,
        question_text: str,
        max_list_items: Optional[int] = None,
        include_comment: bool = True,
        answering_instructions: Optional[str] = None,
        question_presentation: Optional[str] = None,
        permissive: bool = False,
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
        self.permissive = permissive

        self.include_comment = include_comment
        self.answering_instructions = answering_instructions
        self.question_presentations = question_presentation

    def create_response_model(self):
        return create_model(self.max_list_items, self.permissive)

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
    def example(
        cls, include_comment=True, max_list_items=None, permissive=False
    ) -> QuestionList:
        """Return an example of a list question."""
        return cls(
            question_name="list_of_foods",
            question_text="What are your favorite foods?",
            include_comment=include_comment,
            max_list_items=max_list_items,
            permissive=permissive,
        )


def main():
    """Create an example of a list question and demonstrate its functionality."""
    from edsl.questions.QuestionList import QuestionList

    q = QuestionList.example(max_list_items=5)
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
