from __future__ import annotations
import textwrap
import io
from abc import ABC, abstractmethod, ABCMeta
from rich.console import Console
from rich.table import Table
from jinja2 import Template, Environment, meta
from typing import Any, Type
from edsl.exceptions import (
    QuestionResponseValidationError,
    QuestionSerializationError,
    QuestionScenarioRenderError,
)
from edsl.questions.descriptors import (
    InstructionsDescriptor,
    QuestionNameDescriptor,
    QuestionTextDescriptor,
    ShortNamesDictDescriptor,
)

from edsl.prompts.Prompt import Prompt

from edsl.enums import QuestionType

# from edsl.questions.question_registry import get_question_class
from edsl.questions.AnswerValidatorMixin import AnswerValidatorMixin

from edsl.exceptions.questions import QuestionMissingTypeError, QuestionBadTypeError


class RegisterQuestionsMeta(ABCMeta):
    "Metaclass to register output elements in a registry i.e., those that have a parent"
    _registry = {}  # Initialize the registry as a dictionary

    def __init__(cls, name, bases, dct):
        super(RegisterQuestionsMeta, cls).__init__(name, bases, dct)
        if name != "Question":
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
        return cls._registry

    @classmethod
    def question_types_to_classes(
        cls,
    ):
        d = {}
        for classname, cls in cls._registry.items():
            if hasattr(cls, "question_type"):
                d[cls.question_type] = cls
            else:
                raise Exception(
                    f"Class {classname} does not have a question_type class attribute"
                )
        return d


from edsl.Base import PersistenceMixin, RichPrintingMixin


class Question(
    PersistenceMixin,
    RichPrintingMixin,
    ABC,
    AnswerValidatorMixin,
    metaclass=RegisterQuestionsMeta,
):
    """
    ABC for the Question class. All questions should inherit from this class.
    """

    question_name: str = QuestionNameDescriptor()
    question_text: str = QuestionTextDescriptor()
    short_names_dict: dict[str, str] = ShortNamesDictDescriptor()

    @property
    def data(self) -> dict:
        """Returns a dictionary of question attributes **except** for question_type"""
        candidate_data = {
            k.replace("_", "", 1): v
            for k, v in self.__dict__.items()
            if k.startswith("_")
        }
        optional_attributes = {
            "set_instructions": "instructions",
        }
        for boolean_flag, attribute in optional_attributes.items():
            if hasattr(self, boolean_flag) and not getattr(self, boolean_flag):
                candidate_data.pop(attribute, None)

        return candidate_data

    ############################
    # Serialization methods
    ############################
    def to_dict(self) -> dict[str, Any]:
        """Converts the question to a dictionary that includes the question type (used in deserialization)."""
        candidate_data = self.data.copy()
        candidate_data["question_type"] = self.question_type
        return candidate_data

    @classmethod
    def from_dict(cls, data: dict) -> Type[Question]:
        """Constructs a question object from a dictionary created by that question's `to_dict` method."""
        local_data = data.copy()
        try:
            question_type = local_data.pop("question_type")
        except:
            raise QuestionSerializationError(
                f"Data does not have a 'question_type' field (got {data})."
            )
        from edsl.questions.question_registry import get_question_class

        try:
            question_class = get_question_class(question_type)
        except ValueError:
            raise QuestionSerializationError(
                f"No question registered with question_type {question_type}"
            )
        return question_class(**local_data)

    ############################
    # Dunder methods
    ############################
    def __repr__(self) -> str:
        """Returns a string representation of the question. Should be able to be used to reconstruct the question."""
        class_name = self.__class__.__name__
        items = [
            f"{k} = '{v}'" if isinstance(v, str) else f"{k} = {v}"
            for k, v in self.data.items()
            if k != "question_type"
        ]
        return f"{class_name}({', '.join(items)})"

    def __eq__(self, other: Type[Question]) -> bool:
        """Checks if two questions are equal. Equality is defined as having the .to_dict()"""
        if not isinstance(other, Question):
            return False
        return self.to_dict() == other.to_dict()

    # TODO: Throws an error that should be addressed at QuestionFunctional
    def __add__(self, other_question):
        """
        Composes two questions into a single question.
        >>> from edsl.scenarios.Scenario import Scenario
        >>> from edsl.questions.QuestionFreeText import QuestionFreeText
        >>> from edsl.questions.QuestionNumerical import QuestionNumerical
        >>> q1 = QuestionFreeText(question_text = "What is the capital of {{country}}", question_name = "capital")
        >>> q2 = QuestionNumerical(question_text = "What is the population of {{capital}}, in millions. Please round", question_name = "population")
        >>> q3 = q1 + q2
        """
        from edsl.questions import compose_questions

        return compose_questions(self, other_question)

    @abstractmethod
    def validate_answer(self, answer: dict[str, str]):
        pass

    def validate_response(self, response):
        """Validates the response from the LLM"""
        if "answer" not in response:
            raise QuestionResponseValidationError(
                "Response from LLM does not have an answer"
            )
        return response

    @abstractmethod
    def translate_answer_code_to_answer(self):  # pragma: no cover
        """Translates the answer code to the actual answer. Behavior depends on the question type."""
        pass

    @abstractmethod
    def simulate_answer(self, human_readable=True) -> dict:  # pragma: no cover
        """Simulates a valid answer for debugging purposes (what the validator expects)"""
        pass

    ############################
    # Forward methods
    ############################
    def add_question(self, other):
        "Adds a question to this question by turning them into a survey with two questions"
        from edsl.surveys.Survey import Survey

        s = Survey([self, other])
        return s

    def run(self, *args, **kwargs):
        "Turns a single question into a survey and runs it."
        from edsl.surveys.Survey import Survey

        s = Survey([self])
        return s.run(*args, **kwargs)

    def by(self, *args):
        "Documentation missing."
        from edsl.surveys.Survey import Survey

        s = Survey([self])
        return s.by(*args)

    def rich_print(self):
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Question Name", style="dim")
        table.add_column("Question Type")
        table.add_column("Question Text")
        table.add_column("Options")

        question = self
        if hasattr(question, "question_options"):
            options = ", ".join([str(o) for o in question.question_options])
        else:
            options = "None"
        table.add_row(
            question.question_name,
            question.question_type,
            question.question_text,
            options,
        )
        return table


if __name__ == "__main__":
    q = get_question_class("free_text")
