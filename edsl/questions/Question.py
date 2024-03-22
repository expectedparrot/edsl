"""This module contains the Question class, which is the base class for all questions in EDSL.
It provides methods for serializing and deserializing questions, as well as validating answers and responses from the LLM.

Constructing a Question
-----------------------
Key steps:

* Identify a desired question type (multiple choice, free text, etc.) and import the corresponding class. For example: 

.. code-block:: python

    from edsl.questions import QuestionMultipleChoice, QuestionFreeText

* Draft the question text and specify the question name and any answer options for relevant question types (such as multiple choice or checkbox). For example: 

.. code-block:: python

    q1 = QuestionMultipleChoice(
        question_name = "color",
        question_text = "What is your favorite color?",
        question_options = ["Red", "Blue", "Green", "Yellow"]
    )
    q2 = QuestionFreeText(
        question_name = "food",
        question_text = "What is your favorite food?"
    )

* Optionally parameterize the question text using double braces, e.g.: 

.. code-block:: python

    q3 = QuestionFreeText(
        question_name = "favorite_item",
        question_text = "What is your favorite {{ item }}?",
    )

This allows you to create multiple versions of a question that can be administered at once in a survey.
See details about adding question parameters to a survey in the `Scenario <https://docs.expectedparrot.com/en/latest/scenarios.html>`_ module.

Simulating a response
---------------------
* Add the question to a survey or run it directly with the `run` method: 

.. code-block:: python

    results = Survey([q1, q2]).run()
    results = q3.run()

This administers the question to the LLM and returns the response in a `Results` object.
Results can be printed, saved, analyzed and visualized in a variety of built-in methods.
See details about these methods in the `Results <https://docs.expectedparrot.com/en/latest/results.html>`_ module.

See also details about specifying question scenarios, agents and language models in their respective modules:

* `Scenario <https://docs.expectedparrot.com/en/latest/scenarios.html>`_
* `Agent <https://docs.expectedparrot.com/en/latest/agents.html>`_
* `Language Model <https://docs.expectedparrot.com/en/latest/language_models.html>`_



"""
from __future__ import annotations
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
from edsl.questions.AnswerValidatorMixin import AnswerValidatorMixin
from edsl.exceptions.questions import QuestionMissingTypeError, QuestionBadTypeError


class RegisterQuestionsMeta(ABCMeta):
    """Metaclass to register output elements in a registry i.e., those that have a parent."""

    _registry = {}  # Initialize the registry as a dictionary

    def __init__(cls, name, bases, dct):
        """Initialize the class and adds it to the registry if it's not the base class."""
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


from edsl.Base import PersistenceMixin, RichPrintingMixin


class Question(
    PersistenceMixin,
    RichPrintingMixin,
    ABC,
    AnswerValidatorMixin,
    metaclass=RegisterQuestionsMeta,
):
    """ABC for the Question class. All questions should inherit from this class."""

    question_name: str = QuestionNameDescriptor()
    question_text: str = QuestionTextDescriptor()
    short_names_dict: dict[str, str] = ShortNamesDictDescriptor()

    @property
    def data(self) -> dict:
        """Return a dictionary of question attributes **except** for question_type."""
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
        """Convert the question to a dictionary that includes the question type (used in deserialization)."""
        candidate_data = self.data.copy()
        candidate_data["question_type"] = self.question_type
        return candidate_data

    @classmethod
    def from_dict(cls, data: dict) -> Type[Question]:
        """Construct a question object from a dictionary created by that question's `to_dict` method."""
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
        """Return a string representation of the question. Should be able to be used to reconstruct the question."""
        class_name = self.__class__.__name__
        items = [
            f"{k} = '{v}'" if isinstance(v, str) else f"{k} = {v}"
            for k, v in self.data.items()
            if k != "question_type"
        ]
        return f"{class_name}({', '.join(items)})"

    def __eq__(self, other: Type[Question]) -> bool:
        """Check if two questions are equal. Equality is defined as having the .to_dict()."""
        if not isinstance(other, Question):
            return False
        return self.to_dict() == other.to_dict()

    # TODO: Throws an error that should be addressed at QuestionFunctional
    def __add__(self, other_question):
        """
        Compose two questions into a single question.

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
        """Validate the answer from the LLM. Behavior depends on the question type."""
        pass

    def validate_response(self, response):
        """Validate the response from the LLM. Behavior depends on the question type."""
        if "answer" not in response:
            raise QuestionResponseValidationError(
                "Response from LLM does not have an answer"
            )
        return response

    @abstractmethod
    def translate_answer_code_to_answer(self):  # pragma: no cover
        """Translate the answer code to the actual answer. Behavior depends on the question type."""
        pass

    @abstractmethod
    def simulate_answer(self, human_readable=True) -> dict:  # pragma: no cover
        """Simulate a valid answer for debugging purposes (what the validator expects)."""
        pass

    ############################
    # Forward methods
    ############################
    def add_question(self, other: Question) -> 'Survey':
        """Add a question to this question by turning them into a survey with two questions."""
        from edsl.surveys.Survey import Survey

        s = Survey([self, other])
        return s

    def run(self, *args, **kwargs):
        """Turn a single question into a survey and run it."""
        from edsl.surveys.Survey import Survey

        s = Survey([self])
        return s.run(*args, **kwargs)

    def by(self, *args):
        """Turn a single question into a survey and run it."""
        from edsl.surveys.Survey import Survey

        s = Survey([self])
        return s.by(*args)

    def rich_print(self):
        """Print the question in a rich format."""
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
