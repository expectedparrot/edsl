from __future__ import annotations
import random
import textwrap
from jinja2 import Template
from typing import Optional, Union
from edsl.utilities import random_string
from edsl.questions.descriptors import QuestionOptionsDescriptor
from edsl.questions.Question import Question


class QuestionMultipleChoice(Question):
    """QuestionMultipleChoice"""

    question_type = "multiple_choice"
    # Question-specific descriptors
    question_options: list[str] = QuestionOptionsDescriptor()
    default_instructions = textwrap.dedent(
        """\
        You are being asked the following question: {{question_text}}
        The options are 
        {% for option in question_options %}
        {{ loop.index0 }}: {{option}}
        {% endfor %}                       
        Return a valid JSON formatted like this, selecting only the number of the option: 
        {"answer": <put answer code here>, "comment": "<put explanation here>"}
        Only 1 option may be selected.
        """
    )

    def __init__(
        self,
        question_text: str,
        question_options: list[str],
        question_name: str,
        short_names_dict: Optional[dict[str, str]] = None,
        instructions: Optional[str] = None,
    ):
        self.question_text = question_text
        self.question_options = question_options
        self.question_name = question_name
        self.short_names_dict = short_names_dict or dict()
        self.instructions = instructions or self.default_instructions

    def validate_answer(
        self, answer: dict[str, Union[str, int]]
    ) -> dict[str, Union[str, int]]:
        """Validates the answer"""
        self.validate_answer_basic(answer)
        self.validate_answer_multiple_choice(answer)
        return answer

    ################
    # Less important
    ################
    def translate_answer_code_to_answer(self, answer_code, scenario=None):
        """
        Translates the answer code to the actual answer.
        For example, for question_options ["a", "b", "c"], the answer codes are 0, 1, and 2.
        The LLM will respond with 0, and this code will translate that to "a".
        # TODO: REMOVE
        >>> q = QuestionMultipleChoice(question_text = "How are you?", question_options = ["Good", "Great", "OK", "Bad"], question_name = "how_feeling")
        >>> q.translate_answer_code_to_answer(0, {})
        'Good'
        """
        scenario = scenario or dict()
        translated_options = [
            Template(str(option)).render(scenario) for option in self.question_options
        ]
        return translated_options[int(answer_code)]

    def simulate_answer(
        self, human_readable: bool = True
    ) -> dict[str, Union[int, str]]:
        """Simulates a valid answer for debugging purposes"""
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
    def example(cls):
        return cls(
            question_text="How are you?",
            question_options=["Good", "Great", "OK", "Bad"],
            question_name="how_feeling",
            short_names_dict={"Good": "g", "Great": "gr", "OK": "ok", "Bad": "b"},
        )


def main():
    from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice

    q1 = QuestionMultipleChoice(
        question_text="Do you enjoying eating custard while skydiving?",
        question_options=["yes, somtimes", "no", "only on Tuesdays"],
        question_name="goose_fight",
    )
    q2 = QuestionMultipleChoice(
        question_text="Do you enjoying eating custard while skydiving?",
        question_options=["yes, somtimes", "no", "only on Tuesdays"],
        question_name="goose_fight",
        instructions="HEre are are some instructions",
    )

    # q_dict = q.to_dict()
    # print(f"Serialized dictionary:{q_dict}")
    # new_q = Question.from_dict(q_dict)
