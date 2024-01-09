import textwrap

from typing import Optional, Type, Union
from edsl.questions import Question
from edsl.exceptions import QuestionAnswerValidationError
from edsl.utilities.utilities import random_string


class QuestionList(Question):
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

    question_type = "list"

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

        # custom instructions
        if set_instructions := (instructions is not None):
            self.instructions = self.instructions
        else:
            self.instructions = self.default_instructions
        self.set_instructions = set_instructions

        self.allow_nonresponse = allow_nonresponse or False
        self.max_list_items = max_list_items or 10
        self.short_names_dict = short_names_dict or dict()

    #############
    ## Validators
    #############

    def translate_answer_code_to_answer(self, answer, scenario):
        """There is no answer code."""
        return answer

    def check_answer_nonresponse(cls, value):
        if (
            hasattr(self, "allow_nonresponse")
            and self.allow_nonresponse == False
            and (value == [] or value is None)
        ):
            raise QuestionAnswerValidationError("You must provide a response.")

        return value

    def check_answer_length(cls, value):
        if (
            hasattr(self, "max_list_items")
            and self.max_list_items is not None
            and (len(value) > self.max_list_items)
        ):
            raise QuestionAnswerValidationError("Response has too many items.")
        return value

    def check_answer_check(cls, value):
        if any([item == "" for item in value]):
            raise QuestionAnswerValidationError(
                f"Answer cannot contain empty strings, but got {value}."
            )
        return value

    def simulate_answer(self):
        "Simulates a valid answer for debugging purposes (what the validator expects)"
        return {"answer": [random_string(), random_string()]}

    def validate_answer(self, answer: dict[str, str]):
        """Validates the answer"""
        if "answer" not in answer:
            raise QuestionAnswerValidationError("Answer must have an 'answer' key!")
        return answer


def main():  # pragma: no cover
    """This is a demo of how to use the QuestionList. It consumes API calls."""
    from edsl.language_models import LanguageModelOpenAIFour
    from edsl.questions import QuestionList

    m4 = LanguageModelOpenAIFour()

    question = QuestionList(
        question_text="What are some factors that could determine whether someone likes ice cream?",
        question_name="ice_cream_love_attributes",
        max_list_items=20,
    )

    results = question.by(m4).run()
    results.data[0].answer

    question = QuestionList(
        question_text="What are the most beloved sport teams in America?",
        question_name="most_beloved_teams",
        max_list_items=5,
    )

    results = question.by(m4).run()
    results.data[0].answer
