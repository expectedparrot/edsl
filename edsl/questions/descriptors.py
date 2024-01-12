from abc import ABC, abstractmethod
import re
from typing import Any, Callable
from edsl.exceptions import (
    QuestionAnswerValidationError,
    QuestionCreationValidationError,
)
from edsl.questions import Settings
from edsl.utilities import is_valid_variable_name


################################
# Helper functions
################################


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


################################
# Descriptor ABC
################################


class BaseDescriptor(ABC):
    """
    ABC for Descriptors. Descriptors manage Question attribute setting, getting, and validation.
    - `name` is the name of the attribute
    - `owner` is the class to which the attribute belongs

    Workflow:
    - `__set_name__` is called when the descriptor is assigned to a class attribute.
    - `__set__` is called when a value is assigned to the class attribute.
    - `__get__` is called when the class attribute is accessed.
    """

    def __set_name__(self, owner, name: str) -> None:
        """The attribute that the descriptor is managing is stored in the Question's __dict__ with a leading underscore."""
        self.name = f"_{name}"

    def __get__(self, instance, owner) -> Any:
        """Gets the value of the attribute from the Question's__dict__ by respecting the leading underscore."""
        return instance.__dict__[self.name]

    @abstractmethod
    def validate(self, value: Any) -> None:
        """
        Validates a value that's about to be set. Has to be implemented by children descriptors.
        - If the value is valid, do nothing
        - If the value is invalid, raise an exception
        """
        raise NotImplementedError

    def __set__(self, instance, value: Any) -> None:
        """Sets the value of the attribute in the Question's __dict__ by respecting the leading underscore.
        - Validates the value before setting it.
        - For the `_instructions` attribute, also sets the `set_instructions` attribute to be True if the instructions are not the default instructions, else False.
        """
        self.validate(value, instance)
        instance.__dict__[self.name] = value
        if self.name == "_instructions":
            instance.set_instructions = value != instance.default_instructions


################################
# General descriptors
################################


class FunctionDescriptor(BaseDescriptor):
    """Validates that the value is a function."""

    def validate(self, value: Any, instance) -> Callable:
        """Validates the value is a function, and if so, returns it."""
        if not callable(value):
            raise QuestionCreationValidationError(
                f"Expected a function (got {value}).)"
            )
        return value


class IntegerDescriptor(BaseDescriptor):
    """
    Validates that a value is an integer.
    - `none_allowed` is whether None is allowed as a value.
    """

    def __init__(self, none_allowed: bool = False):
        self.none_allowed = none_allowed

    def validate(self, value, instance):
        if self.none_allowed:
            if not (isinstance(value, int) or value is None):
                raise QuestionAnswerValidationError(
                    f"Expected an integer or None (got {value})."
                )
        else:
            if not isinstance(value, int):
                raise QuestionAnswerValidationError(
                    f"Expected an integer (got {value})."
                )


class IntegerOrNoneDescriptor(BaseDescriptor):
    def validate(self, value, instance):
        if not (isinstance(value, int) or value is None):
            raise QuestionCreationValidationError(
                f"Expected an integer or None (got {value})."
            )


class NumericalOrNoneDescriptor(BaseDescriptor):
    def validate(self, value, instance):
        if not is_number_or_none(value):
            raise QuestionAnswerValidationError(
                f"Expected a number or None (got {value})."
            )


################################
# Attribute-specific descriptors
################################


class AllowNonresponseDescriptor(BaseDescriptor):
    """Validates that the `allow_nonresponse` attribute is a boolean."""

    def validate(self, value, instance):
        if not isinstance(value, bool):
            raise QuestionCreationValidationError(
                f"`allow_nonresponse` must be a boolean (got {value})."
            )


class AnswerTemplateDescriptor(BaseDescriptor):
    """Validates that the answer template is a dictionary with string keys and string values."""

    def validate(self, value: Any, instance) -> None:
        if not isinstance(value, dict):
            raise QuestionCreationValidationError(
                f"`answer_template` must be a dictionary (got {value}).)"
            )
        if not all(isinstance(x, str) for x in value.keys()):
            raise QuestionCreationValidationError(
                f"`answer_template` keys must be strings (got {value})."
            )


class InstructionsDescriptor(BaseDescriptor):
    """Validates that the `instructions` attribute is a string."""

    def validate(self, value, instance):
        if not isinstance(value, str):
            raise QuestionCreationValidationError(
                f"Question `instructions` must be a string (got {value})."
            )


class NumSelectionsDescriptor(BaseDescriptor):
    """Validates that `num_selections` is an integer, is less than the number of options, and is positive."""

    def validate(self, value, instance):
        if not (isinstance(value, int)):
            raise QuestionCreationValidationError(
                f"`num_selections` must be an integer (got {value})."
            )
        if value > len(instance.question_options):
            raise QuestionAnswerValidationError(
                f"`num_selections` must be less than the number of options (got {value})."
            )
        if value < 1:
            raise QuestionAnswerValidationError(
                f"`num_selections` must a positive integer (got {value})."
            )


class OptionLabelDescriptor(BaseDescriptor):
    def validate(self, value, instance):
        if value is not None:
            if min(value.keys()) != min(instance.question_options):
                raise QuestionCreationValidationError(
                    f"First option needs a label (got {value})"
                )
            if max(value.keys()) != max(instance.question_options):
                raise QuestionCreationValidationError(
                    f"Last option needs a label (got {value})"
                )
            if not all(isinstance(x, str) for x in value.values()):
                raise QuestionCreationValidationError(
                    "Option labels must be strings (got {value})."
                )
            for key in value.keys():
                if key not in instance.question_options:
                    raise QuestionCreationValidationError(
                        f"Option label key ({key}) is not in question options ({instance.question_options})."
                    )


class QuestionNameDescriptor(BaseDescriptor):
    """Validates that the `question_name` attribute is a valid variable name."""

    def validate(self, value, instance):
        if not is_valid_variable_name(value):
            raise QuestionCreationValidationError(
                f"`question_name` is not a valid variable name (got {value})."
            )


class QuestionOptionsDescriptor(BaseDescriptor):
    """Validates that `question_options` is a list, does not exceed the min/max lengths, and has unique items."""

    def __init__(self, num_choices: int = None, linear_scale: bool = False):
        self.num_choices = num_choices
        self.linear_scale = linear_scale

    def validate(self, value: Any, instance) -> None:
        if not isinstance(value, list):
            raise QuestionCreationValidationError(
                f"Question options must be a list (got {value})."
            )
        if len(value) > Settings.MAX_NUM_OPTIONS:
            raise QuestionCreationValidationError(
                f"Too many question options (got {value})."
            )
        if len(value) < Settings.MIN_NUM_OPTIONS:
            raise QuestionCreationValidationError(
                f"Too few question options (got {value})."
            )
        if len(value) != len(set(value)):
            raise QuestionCreationValidationError(
                f"Question options must be unique (got {value})."
            )
        if not self.linear_scale:
            if not all(isinstance(x, str) for x in value):
                raise QuestionCreationValidationError(
                    "Question options must be strings (got {value}).)"
                )
            if not all(
                [
                    len(option) > 1 and len(option) < Settings.MAX_OPTION_LENGTH
                    for option in value
                ]
            ):
                raise QuestionCreationValidationError(
                    f"All question options must be at least 2 characters long but less than {Settings.MAX_OPTION_LENGTH} characters long (got {value})."
                )

        if hasattr(instance, "min_selections") and instance.min_selections != None:
            if instance.min_selections > len(value):
                raise QuestionCreationValidationError(
                    f"You asked for at least {instance.min_selections} selections, but provided fewer options (got {value})."
                )
        if hasattr(instance, "max_selections") and instance.max_selections != None:
            if instance.max_selections > len(value):
                raise QuestionCreationValidationError(
                    f"You asked for at most {instance.max_selections} selections, but provided fewer options (got {value})."
                )
        if self.num_choices is not None:
            if len(value) != self.num_choices:
                raise QuestionCreationValidationError(
                    f"You asked for {self.num_choices} selections, but provided {len(value)} options."
                )
        if self.linear_scale:
            if sorted(value) != list(range(min(value), max(value) + 1)):
                raise QuestionCreationValidationError(
                    f"LinearScale.question_options must be a list of successive integers, e.g. [1, 2, 3] (got {value})."
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
                f"WARNING: Question text contains a single-braced substring: {value}.\nYou probably mean to use a double-braced substring, e.g. {{variable}}."
            )


class ShortNamesDictDescriptor(BaseDescriptor):
    def validate(self, value, instance):
        "Validates the short names dictionary"
        if not isinstance(value, dict):
            raise QuestionCreationValidationError(
                f"Short names dictionary must be a dictionary (got {value})."
            )
        if not all(isinstance(x, str) for x in value.keys()):
            raise QuestionCreationValidationError(
                f"Short names dictionary keys must be strings (got {value})."
            )
        if not all(isinstance(x, str) for x in value.values()):
            raise QuestionCreationValidationError(
                f"Short names dictionary values must be strings (got {value})."
            )
