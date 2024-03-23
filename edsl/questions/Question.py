"""This module contains the Question class, which is the base class for all questions in EDSL.
It provides methods for serializing and deserializing questions, as well as validating answers and responses from the LLM.

Constructing a Question
-----------------------
Key steps:

* Import the `Question` class and select an appropriate question type. Available question types include multiple choice, checkbox, free text, numerical, linear scale, list, rank, budget, extract, top k, Likert scale, yes/no.

* Import the question type class. For example, to create a multiple choice question:

.. code-block:: python

    from edsl.questions import QuestionMultipleChoice

* Construct a question in the required format. All question types require a question name and question text. Some question types require additional fields, such as question options for multiple choice questions:

.. code-block:: python

    q = QuestionMultipleChoice(
        question_name = "color",
        question_text = "What is your favorite color?",
        question_options = ["Red", "Blue", "Green", "Yellow"]
    )

To see an example of a question type in the required format, use the question type `example()` method:

.. code-block:: python

    QuestionMultipleChoice.example()


Simulating a response
---------------------
Administer the question to an agent with the `run` method. A single question can be run individually by appending the `run` method directly to the question object:

.. code-block:: python

    results = q.run()
    
If the question is part of a survey, the method is appended to the survey object instead:

.. code-block:: python
    
    q1 = ...
    q2 = ...
    results = Survey([q1, q2]).run()

(See more details about surveys in the * :ref:`surveys` module.)


The `run` method administers a question to the LLM and returns the response in a `Results` object.
Results can be printed, saved, analyzed and visualized in a variety of built-in methods.
See details about these methods in the * :ref:`results` module.


Parameterizing a question
-------------------------
Questions can be parameterized to include variables that are replaced with specific values when the question is run.
This allows you to create multiple versions of a question that can be administered at once in a survey.

Key steps:

* Create a question that takes a parameter in double braces:

.. code-block:: python

    from edsl.questions import QuestionFreeText

    q = QuestionFreeText(
        question_name = "favorite_item",
        question_text = "What is your favorite {{ item }}?",
    )

* Create a dictionary for the value that will replace the parameter and store it in a Scenario object:

.. code-block:: python

    scenario = Scenario({"item": "color"})

If multiple values will be used, create multiple Scenario objects in a list:

.. code-block:: python

    scenarios = [Scenario({"item": item}) for item in ["color", "food"]]

* Add the Scenario objects to the question with the `by` method before appending the `run` method:

.. code-block:: python

    results = q.by(scenarios).run()

If the question is part of a survey, add the Scenario objects to the survey:

.. code-block:: python

    q1 = ...
    q2 = ...
    results = Survey([q1, q2]).by(scenarios).run()

As with other Survey components (agents and language models), multiple Scenario objects should be added together as a list in the same `by` method.

Learn more about specifying question scenarios, agents and language models in their respective modules:

* :ref:`scenarios`
* :ref:`agents`
* :ref:`language_models`


Base class methods
------------------
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from rich.table import Table
from typing import Any, Type
from edsl.exceptions import (
    QuestionResponseValidationError,
    QuestionSerializationError,
)
from edsl.questions.descriptors import (
    QuestionNameDescriptor,
    QuestionTextDescriptor,
    ShortNamesDictDescriptor,
)

from edsl.questions.AnswerValidatorMixin import AnswerValidatorMixin
from edsl.questions.RegisterQuestionsMeta import RegisterQuestionsMeta
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
    def _validate_answer(self, answer: dict[str, str]):
        """Validate the answer from the LLM. Behavior depends on the question type."""
        pass

    def _validate_response(self, response):
        """Validate the response from the LLM. Behavior depends on the question type."""
        if "answer" not in response:
            raise QuestionResponseValidationError(
                "Response from LLM does not have an answer"
            )
        return response

    @abstractmethod
    def _translate_answer_code_to_answer(self):  # pragma: no cover
        """Translate the answer code to the actual answer. Behavior depends on the question type."""
        pass

    @abstractmethod
    def _simulate_answer(self, human_readable=True) -> dict:  # pragma: no cover
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
