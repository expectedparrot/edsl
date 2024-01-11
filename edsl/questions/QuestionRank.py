import random
import textwrap
from jinja2 import Template
from typing import Optional
from edsl.questions import Question
from edsl.exceptions import QuestionAnswerValidationError
from edsl.utilities.utilities import random_string
from edsl.questions.descriptors import (
    QuestionOptionsDescriptor,
    NumSelectionsDescriptor,
)


class QuestionRank(Question):
    """
    This question asks the user to rank options from a list.

    Arguments:
    - `question_name` is the name of the question (string)
    - `question_options` are the options the user should select from (list of strings)
    - `question_text` is the text of the question (string)

    Optional arguments:
    - `num_selections` is the number of options that must be selected (positive integer)
    - `instructions` are the instructions for the question (string). If not provided, the default instructions are used. To view them, run `QuestionRank.default_instructions`
    - `short_names_dict` maps question_options to short names (dictionary mapping strings to strings)

    For an example, run `QuestionRank.example()`
    """

    question_type = "rank"
    question_options: list[str] = QuestionOptionsDescriptor()
    num_selections = NumSelectionsDescriptor()
    default_instructions = textwrap.dedent(
        """\
        You are being asked the following question: {{question_text}}
        The options are 
        {% for option in question_options %}
        {{ loop.index0 }}: {{option}}
        {% endfor %}                       
        Return a valid JSON formatted like this, selecting the numbers of the options in order of preference, 
        with the most preferred option first, and the least preferred option last: 
        {"answer": [<put comma-separated list of answer codes here>], "comment": "<put explanation here>"}
        Exactly {{num_selections}} options must be selected.
        """
    )

    def __init__(
        self,
        question_name: str,
        question_text: str,
        question_options: list[str],
        num_selections: Optional[int] = None,
        short_names_dict: Optional[dict[str, str]] = None,
        instructions: Optional[str] = None,
    ):
        self.question_name = question_name
        self.question_text = question_text
        self.question_options = question_options
        self.instructions = instructions or self.default_instructions
        self.short_names_dict = short_names_dict or dict()
        self.num_selections = num_selections or len(question_options)

    def validate_answer(self, answer):
        self.validate_answer_template_basic(answer)
        self.validate_answer_key_value(answer, "answer", list)
        value = answer["answer"]
        acceptable_values = list(range(len(self.question_options)))
        self.check_answers_valid(value, acceptable_values)
        self.check_answers_count(value)
        return answer

    @staticmethod
    def check_answers_valid(value, acceptable_values):
        for v in value:
            try:
                answer_code = int(v)
            except ValueError:
                raise QuestionAnswerValidationError(
                    f"Rank answer {value} has elements that are not integers, namely {v}."
                )
            except TypeError:
                raise QuestionAnswerValidationError(
                    f"Rank answer {value} has elements that are not integers, namely {v}."
                )
            if answer_code not in acceptable_values:
                raise QuestionAnswerValidationError(
                    f"Answer {value} has elements not in {acceptable_values}, namely {v}."
                )

    def check_answers_count(self, value):
        if len(value) != self.num_selections:
            raise QuestionAnswerValidationError(
                f"Rank answer {value}, but exactly {self.num_selections} selections required."
            )

    def translate_answer_code_to_answer(self, answer_codes, scenario):
        """Translates the answer code to the actual answer."""
        if scenario is None:
            scenario = dict()
        translated_options = [
            Template(option).render(scenario) for option in self.question_options
        ]

        translated_codes = []
        for answer_code in answer_codes:
            translated_codes.append(translated_options[int(answer_code)])
        return translated_codes

    def simulate_answer(self, human_readable=True) -> dict[str, str]:
        """Simulates a valid answer for debugging purposes"""
        if human_readable:
            answer = [random.choice(self.question_options)]
        else:
            answer = [random.choice(range(len(self.question_options)))]
        return {
            "answer": answer,
            "comment": random_string(),
        }
