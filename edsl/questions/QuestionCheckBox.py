import random
import textwrap
from jinja2 import Template
from typing import Any, Optional, Union
from edsl.questions import Question
from edsl.questions.descriptors import (
    IntegerDescriptor,
    QuestionOptionsDescriptor,
)
from edsl.utilities import random_string


class QuestionCheckBox(Question):
    """QuestionCheckBox"""

    question_type = "checkbox"
    question_options: list[str] = QuestionOptionsDescriptor()
    min_selections = IntegerDescriptor(none_allowed=True)
    max_selections = IntegerDescriptor(none_allowed=True)

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

    ################
    # Answer methods
    ################
    def validate_answer(self, answer: Any) -> dict[str, Union[int, str]]:
        self.validate_answer_template_basic(answer)
        self.validate_answer_key_value(answer, "answer", list)
        self.validate_answer_checkbox(answer)
        return answer

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

    ################
    # Helpful methods
    ################
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
