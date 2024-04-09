from __future__ import annotations
from abc import ABCMeta

from edsl.enums import QuestionType
from edsl.exceptions.questions import QuestionMissingTypeError, QuestionBadTypeError


class RegisterQuestionsMeta(ABCMeta):
    """Metaclass to register output elements in a registry i.e., those that have a parent."""

    _registry = {}  # Initialize the registry as a dictionary

    def __init__(cls, name, bases, dct):
        """Initialize the class and adds it to the registry if it's not the base class."""
        super(RegisterQuestionsMeta, cls).__init__(name, bases, dct)
        if name != "QuestionBase":
            ## Enforce that all questions have a question_type class attribute
            ## and it comes from our enum of valid question types.
            if not hasattr(cls, "question_type"):
                raise QuestionMissingTypeError(
                    "Question must have a question_type class attribute"
                )

            if not QuestionType.is_value_valid(cls.question_type):
                acceptable_values = [item.value for item in QuestionType]
                raise QuestionBadTypeError(
                    f"""question_type must be one of {QuestionType} values, which are 
                                currently {acceptable_values}"""
                    ""
                )

            RegisterQuestionsMeta._registry[name] = cls

    @classmethod
    def get_registered_classes(cls):
        """Return the registry of registered classes."""
        return cls._registry

    @classmethod
    def question_types_to_classes(
        cls,
    ):
        """Return a dictionary of question types to classes."""
        d = {}
        for classname, cls in cls._registry.items():
            if hasattr(cls, "question_type"):
                d[cls.question_type] = cls
            else:
                raise Exception(
                    f"Class {classname} does not have a question_type class attribute"
                )
        return d
