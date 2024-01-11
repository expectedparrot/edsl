from abc import ABC, abstractmethod
import re
from typing import Any, Callable
from edsl.exceptions import (
    QuestionCreationValidationError,
    QuestionAnswerValidationError,
)
from edsl.questions.settings import Settings
from edsl.utilities.utilities import is_valid_variable_name


def contains_single_braced_substring(s: str) -> bool:
    """Checks if the string contains a substring in single braces."""
    pattern = r"(?<!\{)\{[^{}]+\}(?!\})"
    match = re.search(pattern, s)
    return bool(match)


def is_number(value: Any) -> bool:
    """Checks if an object is a number."""
    return isinstance(value, int) or isinstance(value, float)


def is_number_or_none(value: Any) -> bool:
    """Checks if an object is a number or None."""
    return value is None or is_number(value)


class FunctionDescriptor:
    def validate(self, value: Any, instance) -> Callable:
        """Validates the value is a function, and if so, returns it."""
        if not callable(value):
            raise Exception("Must be a function!")
        return value


class BaseDescriptor(ABC):
    """ABC for something."""

    @abstractmethod
    def validate(self, value: Any) -> None:
        """Validates the value. If it is invalid, raises an exception. If it is valid, does nothing."""
        pass

    def __get__(self, instance, owner):
        """"""
        return instance.__dict__[self.name]

    def __set__(self, instance, value: Any) -> None:
        self.validate(value, instance)
        instance.__dict__[self.name] = value
        if self.name == "_instructions":
            instance.set_instructions = value != instance.default_instructions

    def __set_name__(self, owner, name: str) -> None:
        self.name = "_" + name


class AnswerTemplateDescriptor(BaseDescriptor):
    def validate(self, value: Any, instance) -> None:
        """Validates that the answer template is a dictionary with string keys and string values."""
        if not isinstance(value, dict):
            raise Exception("Answer template must be a dictionary!")
        if not all(isinstance(x, str) for x in value.keys()):
            raise Exception("Answer template keys must be strings!")


class InstructionsDescriptor(BaseDescriptor):
    def validate(self, value, instance):
        if not isinstance(value, str):
            raise Exception("Instructions must be a string!")


class QuestionAllowNonresponseDescriptor(BaseDescriptor):
    def validate(self, value, instance):
        if not isinstance(value, bool):
            raise Exception("Allow nonresponse must be a boolean!")


class QuestionNameDescriptor(BaseDescriptor):
    def validate(self, value, instance):
        if not is_valid_variable_name(value):
            raise Exception("Question name is not a valid variable name!")


class QuestionOptionsDescriptor(BaseDescriptor):
    def __init__(self, num_choices: int = None, linear_scale: bool = False):
        self.num_choices = num_choices
        self.linear_scale = linear_scale

    def validate(self, value: Any, instance) -> None:
        """Validates that question options is a list, does not exceed the min/max lengths, and has unique items."""
        if not isinstance(value, list):
            raise Exception(f"Question options must be a list (got {type(value)}).")
        if len(value) > Settings.MAX_NUM_OPTIONS:
            raise Exception(f"Too many question options (got {len(value)}).")
        if len(value) < Settings.MIN_NUM_OPTIONS:
            raise Exception(f"Too few question options (got {len(value)}).")
        if len(value) != len(set(value)):
            raise Exception(f"Question options must be unique (got {value}).")
        if not self.linear_scale:
            if not all(isinstance(x, str) for x in value):
                raise Exception("Question options must be strings!")
            if not all(
                [
                    len(option) > 1 and len(option) < Settings.MAX_OPTION_LENGTH
                    for option in value
                ]
            ):
                raise Exception(
                    f"All question options must be at least 2 characters long but less than {Settings.MAX_OPTION_LENGTH} characters long!"
                )

        if hasattr(instance, "min_selections") and instance.min_selections != None:
            if instance.min_selections > len(value):
                raise QuestionCreationValidationError(
                    f"You asked for at least {instance.min_selections} selections, but provided {len(value)} options."
                )
        if hasattr(instance, "max_selections") and instance.max_selections != None:
            if instance.max_selections > len(value):
                raise QuestionCreationValidationError(
                    f"You asked for at most {instance.max_selections} selections, but provided {len(value)} options."
                )
        if self.num_choices is not None:
            if len(value) != self.num_choices:
                raise QuestionCreationValidationError(
                    f"You asked for {self.num_choices} selections, but provided {len(value)} options."
                )
        if self.linear_scale:
            if sorted(value) != list(range(min(value), max(value) + 1)):
                raise QuestionCreationValidationError(
                    f"LinearScale.question_options must be a list of successive integers, e.g. [1, 2, 3]"
                )


class QuestionTextDescriptor(BaseDescriptor):
    def validate(self, value, instance):
        if len(value) > Settings.MAX_QUESTION_LENGTH:
            raise Exception("Question is too long!")
        if len(value) < 1:
            raise Exception("Question is too short!")
        if not isinstance(value, str):
            raise Exception("Question must be a string!")
        if contains_single_braced_substring(value):
            print(
                """WARNING: Question text contains a single-braced substring: {value}. 
                You probably mean to use a double-braced substring, e.g. {{variable}}."""
            )


class ShortNamesDictDescriptor(BaseDescriptor):
    def validate(self, value, instance):
        "Validates the short names dictionary"
        if not isinstance(value, dict):
            raise Exception("Short names dictionary must be a dictionary!")
        if not all(isinstance(x, str) for x in value.keys()):
            raise Exception("Short names dictionary keys must be strings!")
        if not all(isinstance(x, str) for x in value.values()):
            raise Exception("Short names dictionary values must be strings!")


class OptionLabelDescriptor(BaseDescriptor):
    def validate(self, value, instance):
        if value is not None:
            if min(value.keys()) != min(instance.question_options):
                raise QuestionCreationValidationError(f"First option needs a label")
            if max(value.keys()) != max(instance.question_options):
                raise QuestionCreationValidationError(f"Last option needs a label")
            if not all(isinstance(x, str) for x in value.values()):
                raise QuestionCreationValidationError("Option labels must be strings!")
            for key in value.keys():
                if key not in instance.question_options:
                    raise QuestionCreationValidationError(
                        f"Option label key {key} is not in question options {instance.question_options}"
                    )


class IntegerOrNoneDescriptor(BaseDescriptor):
    def validate(self, value, instance):
        if not (isinstance(value, int) or value is None):
            raise Exception("Value must be a number!")


class NumSelectionsDescriptor(BaseDescriptor):
    def validate(self, value, instance):
        if not (isinstance(value, int)):
            raise Exception("Value must be a number!")
        if value is not None:
            if value > len(instance.question_options):
                # raise Exception("Value must be less than the number of options!")
                raise QuestionAnswerValidationError(
                    "Value must be less than the number of options!"
                )
            if value < 1:
                raise Exception("Value must be greater than 0!")


class IntegerDescriptor(BaseDescriptor):
    def __init__(self, none_allowed=False):
        self.none_allowed = none_allowed

    def validate(self, value, instance):
        if self.none_allowed:
            if not (isinstance(value, int) or value is None):
                raise Exception("Value must be a number!")
        else:
            if not isinstance(value, int):
                raise Exception("Value must be a number!")


class NumericalOrNoneDescriptor(BaseDescriptor):
    def validate(self, value, instance):
        if not is_number_or_none(value):
            raise Exception("Value must be a number!")
