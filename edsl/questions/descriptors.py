from abc import ABC, abstractmethod
from edsl.utilities.utilities import is_valid_variable_name

from edsl.questions.settings import Settings

from edsl.exceptions import (
    QuestionCreationValidationError,
    QuestionAnswerValidationError,
)


def is_number(value):
    return isinstance(value, int) or isinstance(value, float)


def is_number_or_none(value):
    return value is None or is_number(value)


class BaseDescriptor(ABC):
    @abstractmethod
    def validate(self, value) -> None:
        pass

    def __get__(self, instance, owner):
        return instance.__dict__[self.name]

    def __set__(self, instance, value):
        self.validate(value, instance)
        instance.__dict__[self.name] = value
        instance.set_instructions = self.name == "_instructions"

    def __set_name__(self, owner, name):
        self.name = "_" + name


class QuestionNameDescriptor(BaseDescriptor):
    def validate(self, value, instance):
        if not is_valid_variable_name(value):
            raise Exception("Question name is not a valid variable name!")


class QuestionAllowNonresponseDescriptor(BaseDescriptor):
    def validate(self, value, instance):
        if not isinstance(value, bool):
            raise Exception("Allow nonresponse must be a boolean!")


class QuestionTextDescriptor(BaseDescriptor):
    def validate(self, value, instance):
        if len(value) > Settings.MAX_QUESTION_LENGTH:
            raise Exception("Question is too long!")
        if len(value) < 1:
            raise Exception("Question is too short!")
        if not isinstance(value, str):
            raise Exception("Question must be a string!")


class ShortNamesDictDescriptor(BaseDescriptor):
    def validate(self, value, instance):
        "Validates the short names dictionary"
        if not isinstance(value, dict):
            raise Exception("Short names dictionary must be a dictionary!")
        if not all(isinstance(x, str) for x in value.keys()):
            raise Exception("Short names dictionary keys must be strings!")
        if not all(isinstance(x, str) for x in value.values()):
            raise Exception("Short names dictionary values must be strings!")


class InstructionsDescriptor(BaseDescriptor):
    def validate(self, value, instance):
        if not isinstance(value, str):
            raise Exception("Instructions must be a string!")


class QuestionOptionsDescriptor(BaseDescriptor):
    def validate(self, value, instance):
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

        if hasattr(instance, "min_selections") and instance.min_selections != None:
            if self.min_selections > len(value):
                raise QuestionCreationValidationError(
                    f"You asked for at least {self.min_selections} selections, but provided {len(value)} options."
                )
        if hasattr(instance, "max_selections") and instance.max_selections != None:
            if instance.max_selections > len(value):
                raise QuestionCreationValidationError(
                    f"You asked for at most {instance.max_selections} selections, but provided {len(value)} options."
                )
        return value


class IntegerOrNoneDescriptor(BaseDescriptor):
    def validate(self, value, instance):
        if not (isinstance(value, int) or value is None):
            raise Exception("Value must be a number!")


class NumericalOrNoneDescriptor(BaseDescriptor):
    def validate(self, value, instance):
        if not is_number_or_none(value):
            raise Exception("Value must be a number!")
