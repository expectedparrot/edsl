import random
import textwrap
from typing import Type, Optional

from jinja2 import Template

from edsl.questions import Question, QuestionData, AnswerData, Settings
from edsl.exceptions import (
    QuestionAnswerValidationError,
    QuestionCreationValidationError,
)
from edsl.utilities.utilities import random_string

from edsl.questions.descriptors import (
    QuestionOptionsDescriptor,
    IntegerDescriptor,
    NumSelectionsDescriptor,
)


class QuestionRank(Question):
    question_type = "rank"
    question_options: list[str] = QuestionOptionsDescriptor()
    # num_selections = IntegerDescriptor(none_allowed=False)
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
        short_names_dict: dict[str, str] = None,
        instructions: str = None,
    ):
        self.question_name = question_name
        self.question_text = question_text
        self.question_options = question_options
        self.instructions = instructions or self.default_instructions
        self.short_names_dict = short_names_dict or dict()

        self.num_selections = num_selections or len(question_options)

    def validate_answer(self, answer):
        if "answer" not in answer:
            raise QuestionAnswerValidationError("Answer must have an 'answer' key!")
        value = answer["answer"]
        if not isinstance(value, list):
            raise QuestionAnswerValidationError(f"Rank answer {value} is not a list.")
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

    # def check_answers_valid(self, value):
    #     acceptable_values = list(range(len(self.question_options)))
    #     for v in value:
    #         answer_code = int(v)
    #         if answer_code not in acceptable_values:
    #             raise QuestionAnswerValidationError(
    #                 f"Rank answer {value} has elements not in {acceptable_values}, namely {v}"
    #             )

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
