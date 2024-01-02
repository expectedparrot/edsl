import random
import textwrap
from jinja2 import Template
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, Type
from edsl.questions import Question, QuestionData, AnswerData, Settings
from edsl.exceptions import (
    QuestionCreationValidationError,
    QuestionAnswerValidationError,
)
from edsl.utilities.utilities import random_string


class QuestionCheckBox(QuestionData):
    """Pydantic data model for QuestionCheckBox"""

    question_options: list[str] = Field(
        ...,
        min_length=Settings.MIN_NUM_OPTIONS,
        max_length=Settings.MAX_NUM_OPTIONS,
    )
    min_selections: Optional[int] = None
    max_selections: Optional[int] = None

    # see QuestionFreeText for an explanation of how __new__ works
    def __new__(cls, *args, **kwargs) -> "QuestionCheckBoxEnhanced":
        instance = super(QuestionCheckBox, cls).__new__(cls)
        instance.__init__(*args, **kwargs)
        return QuestionCheckBoxEnhanced(instance)

    @model_validator(mode="after")
    def check_options_count(self):
        if (
            hasattr(self, "question_options")
            and hasattr(self, "min_selections")
            and self.min_selections != None
        ):
            if self.min_selections > len(self.question_options):
                raise QuestionCreationValidationError(
                    f"You asked for at least {self.min_selections} selections, but provided {len(self.question_options)} options."
                )
        if (
            hasattr(self, "question_options")
            and hasattr(self, "max_selections")
            and self.max_selections != None
        ):
            if self.max_selections > len(self.question_options):
                raise QuestionCreationValidationError(
                    f"You asked for at most {self.max_selections} selections, but provided {len(self.question_options)} options."
                )
        return self

    @field_validator("question_options")
    def check_unique(cls, value):
        return cls.base_validator_check_unique(value)

    @field_validator("question_options")
    def check_option_string_lengths(cls, value):
        return cls.base_validator_check_option_string_lengths(value)


class QuestionCheckBoxEnhanced(Question):
    question_type = "checkbox"

    def __init__(self, question: BaseModel):
        super().__init__(question)

    @property
    def instructions(self) -> str:
        # make the min/max conditional parts of the instructions {% if ... end if}
        # if no min_value then default = 1 option must be selected
        return textwrap.dedent(
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

    def construct_answer_data_model(self) -> Type[BaseModel]:
        acceptable_values = range(len(self.question_options))

        class QuestionCheckBoxAnswerDataModel(AnswerData):
            answer: list[int]

            @field_validator("answer")
            def check_answers_valid(cls, value):
                if all([v in acceptable_values for v in value]):
                    return value
                else:
                    raise QuestionAnswerValidationError(
                        f"Answer {value} has elements not in {acceptable_values}."
                    )

            @field_validator("answer")
            def check_answers_count(cls, value):
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

        return QuestionCheckBoxAnswerDataModel

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

    def form_elements(self):
        html_output = f"\n\n\n<label>{self.question_text}</label>\n"
        for index, option in enumerate(self.question_options):
            html_output += f"""<div id = "{self.question_name}_div_{index}">
            <input type="checkbox" id="{self.question_name}_{index}" name="{self.question_name}" value="{option}">
            <label for="{self.question_name}_{index}">{option}</label>
            </div>\n"""
        return html_output
