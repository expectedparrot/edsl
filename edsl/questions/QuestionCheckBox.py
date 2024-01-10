import random
import textwrap
from typing import Optional, Type

from jinja2 import Template

from edsl.questions import Question, Settings

from edsl.exceptions import (
    QuestionCreationValidationError,
    QuestionAnswerValidationError,
)
from edsl.utilities.utilities import random_string


class QuestionCheckBox(Question):
    """QuestionCheckBox"""

    question_type = "checkbox"

    default_instructions = textwrap.dedent(
        """\
        You are being asked the following question: {{question_text}}
        The options are 
        {% for option in question_options %}
        {{ loop.index0 }}: {{option}}
        {% endfor %}                       
        Return a valid JSON formatted like this, selecting only the number of the option: 
        {"answer": [<put comma-separated list of answer codes here>], "comment": "<put explanation here>"}
        {% if min_selections != None and max_selections != None and min_selections == max_selections %}
        You must select exactly {{min_selections}} options.
        {% elif min_selections != None and max_selections != None %}
        Minimum number of options that must be selected: {{min_selections}}.      
        Maximum number of options that must be selected: {{max_selections}}.
        {% elif min_selections != None %}
        Minimum number of options that must be selected: {{min_selections}}.      
        {% elif max_selections != None %}
        Maximum number of options that must be selected: {{max_selections}}.      
        {% endif %}        
        """
    )

    def __init__(
        self,
        question_name: str,
        question_text: str,
        question_options: list[str],
        short_names_dict: Optional[dict[str, str]] = None,
        min_selections: Optional[int] = None,
        max_selections: Optional[int] = None,
        instructions: Optional[str] = None,
    ):
        self.question_name = question_name
        self.question_text = question_text

        self.min_selections = min_selections
        self.max_selections = max_selections

        self.question_options = question_options

        self.short_names_dict = short_names_dict or dict()

        self.instructions = instructions or self.default_instructions
        self.set_instructions = instructions is not None

    # def check_options_count(self):
    #     if (
    #         hasattr(self, "question_options")
    #         and hasattr(self, "min_selections")
    #         and self.min_selections != None
    #     ):
    #         if self.min_selections > len(self.question_options):
    #             raise QuestionCreationValidationError(
    #                 f"You asked for at least {self.min_selections} selections, but provided {len(self.question_options)} options."
    #             )
    #     if (
    #         hasattr(self, "question_options")
    #         and hasattr(self, "max_selections")
    #         and self.max_selections != None
    #     ):
    #         if self.max_selections > len(self.question_options):
    #             raise QuestionCreationValidationError(
    #                 f"You asked for at most {self.max_selections} selections, but provided {len(self.question_options)} options."
    #             )
    #     return self

    def validate_answer(self, value):
        """Validates the answer"""
        self.check_answers_valid(value)
        self.check_answers_count(value)
        return value

    def check_answers_valid(self, value):
        acceptable_values = list(range(len(self.question_options)))
        if all([v in acceptable_values for v in value]):
            return value
        else:
            raise QuestionAnswerValidationError(
                f"Answer {value} has elements not in {acceptable_values}."
            )

    def check_answers_count(self, value):
        # If min or max numbers of option selections are specified, check they are satisfied
        if self.min_selections is not None and len(value) < self.min_selections:
            raise QuestionAnswerValidationError(
                f"Answer {value} has fewer than {self.min_selections} options selected."
            )
        if self.max_selections is not None and len(value) > self.max_selections:
            raise QuestionAnswerValidationError(
                f"Answer {value} has more than {self.max_selections} options selected."
            )
        return value

    ################
    # Less important
    ################
    def translate_answer_code_to_answer(self, answer_codes, scenario):
        """
        Translates the answer code to the actual answer.
        For example, for question options ["a", "b", "c"],the answer codes are 0, 1, and 2.
        The LLM will respond with [0,1] and this code will translate it to ["a","b"].
        """
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
            answer = {
                "answer": [random.choice(self.question_options)],
                "comment": random_string(),
            }
        else:
            answer = {
                "answer": [random.choice(range(len(self.question_options)))],
                "comment": random_string(),
            }
        return answer

    @classmethod
    def example(cls):
        return cls(
            question_name="example_question_name",
            question_text="example_question_text",
            question_options=["option1", "option2"],
            min_selections=1,
            max_selections=1,
        )


if __name__ == "__main__":
    q = QuestionCheckBox.example()
