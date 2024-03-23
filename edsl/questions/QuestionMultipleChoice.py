"""A subclass of the `Question` class for creating multiple choice questions where the response is a single option selected from a list of options.
Example usage:

.. code-block:: python

    from edsl.questions import QuestionMultipleChoice

    q = QuestionMultipleChoice(
        question_name = "color",
        question_text = "What is your favorite color?",
        question_options = ["Red", "Blue", "Green", "Yellow"]
    )

An example can also created using the `example` method:

.. code-block:: python

    QuestionMultipleChoice.example()

"""
from __future__ import annotations
from typing import Optional, Union
import random

from jinja2 import Template

from edsl.utilities import random_string
from edsl.questions.descriptors import QuestionOptionsDescriptor
from edsl.questions.Question import Question
from edsl.scenarios import Scenario

class QuestionMultipleChoice(Question):
    """This question prompts the agent to select one option from a list of options."""

    question_type = "multiple_choice"
    purpose = "When options are known and limited"
    question_options: list[str] = QuestionOptionsDescriptor()

    def __init__(
        self,
        question_name: str,
        question_text: str,
        question_options: list[str],
        short_names_dict: Optional[dict[str, str]] = None,
    ):
        """Instantiate a new QuestionMultipleChoice.

        :param question_name: The name of the question.
        :param question_text: The text of the question.
        :param question_options: The options the agent should select from.
        :param instructions: Instructions for the question. If not provided, the default instructions are used. To view them, run `QuestionMultipleChoice.default_instructions`.
        """
        self.question_name = question_name
        self.question_text = question_text
        self.question_options = question_options
        self.short_names_dict = short_names_dict or dict()

    ################
    # Answer methods
    ################
    def _validate_answer(
        self, answer: dict[str, Union[str, int]]
    ) -> dict[str, Union[str, int]]:
        """Validate the answer."""
        self._validate_answer_template_basic(answer)
        self._validate_answer_multiple_choice(answer)
        return answer

    def _translate_answer_code_to_answer(self, answer_code, scenario: Scenario = None):
        """Translate the answer code to the actual answer."""
        scenario = scenario or Scenario()
        translated_options = [
            Template(str(option)).render(scenario) for option in self.question_options
        ]
        return translated_options[int(answer_code)]

    def _simulate_answer(
        self, human_readable: bool = True
    ) -> dict[str, Union[int, str]]:
        """Simulate a valid answer for debugging purposes."""
        if human_readable:
            answer = random.choice(self.question_options)
        else:
            answer = random.choice(range(len(self.question_options)))
        return {
            "answer": answer,
            "comment": random_string(),
        }

    ################
    # Example
    ################
    @classmethod
    def example(cls) -> QuestionMultipleChoice:
        """Return an example instance."""
        return cls(
            question_text="How are you?",
            question_options=["Good", "Great", "OK", "Bad"],
            question_name="how_feeling",
            short_names_dict={"Good": "g", "Great": "gr", "OK": "ok", "Bad": "b"},
        )


def main():
    """Create an example QuestionMultipleChoice and test its methods."""
    from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice

    q = QuestionMultipleChoice.example()
    q.question_text
    q.question_options
    q.question_name
    q.short_names_dict
    # validate an answer
    q._validate_answer({"answer": 0, "comment": "I like custard"})
    # translate answer code
    q._translate_answer_code_to_answer(0, {})
    # simulate answer
    q._simulate_answer()
    q._simulate_answer(human_readable=False)
    # serialization (inherits from Question)
    q.to_dict()
    assert q.from_dict(q.to_dict()) == q
