import random
import textwrap
from jinja2 import Template
from pydantic import BaseModel, Field, field_validator, model_validator, root_validator
from typing import Type
from edsl.questions import Question, QuestionData, AnswerData, Settings
from edsl.exceptions import (
    QuestionAnswerValidationError,
    QuestionCreationValidationError,
)
from edsl.utilities.utilities import random_string


class QuestionRank(QuestionData):
    """Pydantic data model for QuestionRank"""

    question_options: list[str] = Field(
        ...,
        min_length=Settings.MIN_NUM_OPTIONS,
        max_length=Settings.MAX_NUM_OPTIONS,
    )
    # default = len(question_options) through set_default_num_selections
    num_selections: int = None

    def __new__(cls, *args, **kwargs) -> "QuestionRankEnhanced":
        # see QuestionFreeText for an explanation of how __new__ works
        instance = super(QuestionRank, cls).__new__(cls)
        instance.__init__(*args, **kwargs)
        return QuestionRankEnhanced(instance)

    @root_validator(pre=True)
    def set_default_num_selections(cls, values):
        if "num_selections" not in values or values["num_selections"] is None:
            if "question_options" in values:
                values["num_selections"] = len(values["question_options"])
        return values

    @field_validator("question_options")
    def check_unique(cls, value):
        return cls.base_validator_check_unique(value)

    @field_validator("question_options")
    def check_option_string_lengths(cls, value):
        return cls.base_validator_check_option_string_lengths(value)

    @model_validator(mode="after")
    def check_options_count(self):
        if self.num_selections > len(self.question_options):
            raise QuestionCreationValidationError(
                f"Required selections = {self.num_selections}, but there are only {len(self.question_options)} options."
            )
        return self


class QuestionRankEnhanced(Question):
    question_type = "rank"

    def __init__(self, question: BaseModel):
        super().__init__(question)

    @property
    def instructions(self) -> str:
        return textwrap.dedent(
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

    def construct_answer_data_model(self) -> Type[BaseModel]:
        acceptable_values = range(len(self.question_options))

        class QuestionRankAnswerDataModel(AnswerData):
            answer: list[int]

            @field_validator("answer")
            def check_answers_valid(cls, value):
                if all([v in acceptable_values for v in value]):
                    return value
                else:
                    raise QuestionAnswerValidationError(
                        f"Rank answer {value} has elements not in {acceptable_values}."
                    )

            @field_validator("answer")
            def check_answers_count(cls, value):
                if len(value) != self.num_selections:
                    raise QuestionAnswerValidationError(
                        f"Rank answer {value}, but exactly {self.num_selections} selections required."
                    )
                return value

        return QuestionRankAnswerDataModel

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

    def form_elements(self):
        # TODO: revise this to not use dropdown? Need to collect selections
        html_output = f"\n\n\n<label>{self.question_text}</label>\n"
        for index, option in enumerate(self.question_options):
            html_output += f"""<div id = "{self.question_name}_div_{index}">
            <label for="{self.question_name}_{index}">{option}</label>
            <select id="{self.question_name}_{index}" name="{self.question_name}_{index}">
            """
            for rank in range(1, self.num_selections + 1):
                html_output += f'    <option value="{rank}">{rank}</option>\n'
            html_output += "  </select>\n</div>\n"

        return html_output
