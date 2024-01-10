import weakref
from typing import Union, Type
from edsl.utilities.utilities import is_valid_variable_name
from edsl.questions.settings import Settings

from edsl.exceptions import (
    QuestionCreationValidationError,
    QuestionAnswerValidationError,
)


class QuestionNameDescriptor:
    def __init__(self):
        pass

    def __get__(self, instance, owner):
        return instance.__dict__[self.name]

    def __set__(self, instance, value):
        if not is_valid_variable_name(value):
            raise Exception("Question name is not a valid variable name!")
        instance.__dict__[self.name] = value

    def __set_name__(self, owner, name):
        self.name = "_" + name


def is_number(value):
    return isinstance(value, int) or isinstance(value, float)


def is_number_or_none(value):
    return value is None or is_number(value)


class ValidatorMixin:
    def check_options_count(self, value):
        if hasattr(self, "min_selections") and self.min_selections != None:
            if self.min_selections > len(value):
                raise QuestionCreationValidationError(
                    f"You asked for at least {self.min_selections} selections, but provided {len(value)} options."
                )
        if hasattr(self, "max_selections") and self.max_selections != None:
            if self.max_selections > len(value):
                raise QuestionCreationValidationError(
                    f"You asked for at most {self.max_selections} selections, but provided {len(value)} options."
                )
        return value

    def validate_min_selections(self, value):
        if not is_number_or_none(value):
            raise Exception("Min selections must be a number!")
        return value

    def validate_max_selections(self, value):
        if not is_number_or_none(value):
            raise Exception("Max selections must be a number!")
        return value

    def validate_question_name(self, value):
        if not is_valid_variable_name(value):
            raise Exception("Question name is not a valid variable name!")
        return value

    def validate_min_value(self, value):
        if not is_number_or_none(value):
            raise Exception("Min value must be a number!")
        return value

    def validate_max_value(self, value):
        if not is_number_or_none(value):
            raise Exception("Max value must be a number!")
        return value

    def validate_instructions(self, value):
        if not isinstance(value, str):
            raise Exception("Instructions must be a string!")
        return value

    def validate_question_text(self, value):
        "Validates the question text"
        if len(value) > 1000:
            raise Exception("Question is too long!")
        if len(value) < 1:
            raise Exception("Question is too short!")
        if not isinstance(value, str):
            raise Exception("Question must be a string!")
        return value

    def validate_question_options(self, value):
        "Validates the question options"
        if not isinstance(value, list):
            raise Exception("Question options must be a list!")
        if len(value) > Settings.MAX_NUM_OPTIONS:
            raise Exception("Question options are too long!")
        if len(value) < Settings.MIN_NUM_OPTIONS:
            raise Exception("Question options are too short!")
        if not all(isinstance(x, str) for x in value):
            raise Exception("Question options must be strings!")
        if len(value) != len(set(value)):
            raise Exception("Question options must be unique!")
        if not all([len(option) > 1 for option in value]):
            raise Exception("All question options must be at least 2 characters long!")
        self.check_options_count(value)
        return value

    def validate_short_names_dict(self, value):
        "Validates the short names dictionary"
        if not isinstance(value, dict):
            raise Exception("Short names dictionary must be a dictionary!")
        if not all(isinstance(x, str) for x in value.keys()):
            raise Exception("Short names dictionary keys must be strings!")
        if not all(isinstance(x, str) for x in value.values()):
            raise Exception("Short names dictionary values must be strings!")
        return value

    def validate_allow_nonresponse(self, value):
        "Validates the non response"
        if not isinstance(value, bool):
            raise Exception("Non response must be a boolean!")
        return value

    def validate_max_list_items(self, value):
        "Validates the max list items"
        if not is_number_or_none(value):
            raise Exception("Max list items must be a number!")
        return value

    def validate_answer_basic(self, answer: dict[str, Union[str, int]]) -> None:
        """Checks that the answer is a dictionary with an answer key"""
        if not isinstance(answer, dict):
            raise QuestionAnswerValidationError(
                f"Answer must be a dictionary (got {answer})."
            )
        if not "answer" in answer:
            raise QuestionAnswerValidationError(
                f"Answer must have an 'answer' key (got {answer})."
            )

    def validate_answer_multiple_choice(
        self, answer: dict[str, Union[str, int]]
    ) -> None:
        """Checks that answer["answer"] is a valid answer code for a multiple choice question"""
        try:
            answer_code = int(answer["answer"])
        except:
            raise QuestionAnswerValidationError(
                f"Answer code must be a string, a bytes-like object or a real number (got {answer['answer']})."
            )
        if not answer_code >= 0:
            raise QuestionAnswerValidationError(
                f"Answer code must be a non-negative integer (got {answer_code})."
            )
        if int(answer_code) not in range(len(self.question_options)):
            raise QuestionAnswerValidationError(
                f"Answer code {answer_code} must be in {list(range(len(self.question_options)))}."
            )
