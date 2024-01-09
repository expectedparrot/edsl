import random
import textwrap
from jinja2 import Template
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Type
from edsl.questions import Question, QuestionData, AnswerData, Settings
from edsl.exceptions import QuestionAnswerValidationError
from edsl.utilities.utilities import random_string


class QuestionMultipleChoice(Question):
    """QuestionMultipleChoice"""

    question_type = "multiple_choice"

    def __init__(
        self, question_name: str, question_text: str, question_options: list[str]
    ):
        self.question_name = question_name
        self.question_text = question_text
        self.question_options = question_options

    @property
    def question_text(self):
        return self._question_text

    @question_text.setter
    def question_text(self, question_text):
        if len(question_text) > 1000:
            raise ValueError("Question text is too long")
        self._question_text = question_text


if __name__ == "__main__":
    q = QuestionMultipleChoice(
        question_text="Do you enjoying eating custard while skydiving?",
        question_options=["yes, somtimes", "no", "only on Tuesdays"],
        question_name="goose_fight",
    )
