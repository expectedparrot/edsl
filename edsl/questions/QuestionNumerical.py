import re
import textwrap
from random import randint
from typing import Optional

from edsl.questions import Question
from edsl.exceptions import QuestionAnswerValidationError
from edsl.utilities.utilities import random_string


class QuestionNumerical(Question):
    question_type = "numerical"

    default_instructions = textwrap.dedent(
        """\
        You are being asked a question that requires a numerical response 
        in the form of an integer or decimal (e.g., -12, 0, 1, 2, 3.45, ...).
        
        Your response must be in the following format:
        {"answer": "<your numerical answer here>", "comment": "<your explanation here"}

        You must only include an integer or decimal in the quoted "answer" part of your response. 

        Here is an example of a valid response:
        {"answer": "100", "comment": "This is my explanation..."}

        Here is an example of a response that is invalid because the "answer" includes words:
        {"answer": "I don't know.", "comment": "This is my explanation..."}

        If your response is equivalent to zero, your formatted response should look like this:
        {"answer": "0", "comment": "This is my explanation..."}
        
        You are being asked the following question: {{question_text}}
        {% if min_value is not none %}
        Minimum answer value: {{min_value}}
        {% endif %}
        {% if max_value is not none %}
        Maximum answer value: {{max_value}}
        {% endif %}
        """
    )
    # """
    # Simpler default prompt that works with GPT-4:

    # You are being asked the following question: {{question_text}}
    # {% if min_value is not none %}
    # Minimum answer value: {{min_value}}
    # {% endif %}
    # {% if max_value is not none %}
    # Maximum answer value: {{max_value}}
    # {% endif %}
    # Return a valid JSON formatted like this:
    # {"answer": "<put integer or float answer here>", "comment": "<put explanation here>"}
    # """

    def __init__(
        self,
        question_name: str,
        question_text: str,
        min_value=None,
        max_value=None,
        short_names_dict: Optional[dict[str, str]] = None,
        instructions: Optional[str] = None,
    ):
        self.question_name = question_name
        self.question_text = question_text
        self.min_value = min_value
        self.max_value = max_value

        if set_instructions := (instructions is not None):
            self.instructions = instructions
        else:
            self.instructions = self.default_instructions
        self.set_instructions = set_instructions

        self.short_names_dict = short_names_dict or dict()

    def validate_answer(self, answer: dict[str, str]):
        if "answer" not in answer:
            raise QuestionAnswerValidationError("Answer must have an 'answer' key!")
        value = answer["answer"]
        # if value is None:
        #    raise QuestionAnswerValidationError("Answer must have a value!")
        value = self.check_answer_numeric(value)
        value = self.check_answer(value)
        return answer

    @property
    def min_value(self):
        return self._min_value

    @min_value.setter
    def min_value(self, value):
        self._min_value = self.validate_min_value(value)

    @property
    def max_value(self):
        return self._max_value

    @max_value.setter
    def max_value(self, value):
        self._max_value = self.validate_max_value(value)

    def check_answer_numeric(cls, value):
        if type(value) == str:
            value = value.replace(",", "")
            value = "".join(re.findall(r"[-+]?\d*\.\d+|\d+", value))
            if value.isdigit():
                value = int(value)
            else:
                try:
                    float(value)
                    value = float(value)
                except ValueError:
                    raise QuestionAnswerValidationError(
                        f"Answer should be numerical (int or float)."
                    )
            return value
        elif type(value) == int or type(value) == float:
            return value
        else:
            raise QuestionAnswerValidationError(
                f"Answer should be numerical (int or float)."
            )

    def check_answer(self, value):
        if self.min_value is not None and value < self.min_value:
            raise QuestionAnswerValidationError(
                f"Value {value} is less than {self.min_value}"
            )
        if self.max_value is not None and value > self.max_value:
            raise QuestionAnswerValidationError(
                f"Value {value} is greater than {self.max_value}"
            )
        return value

    def translate_answer_code_to_answer(self, answer, scenario=None):
        """There is no answer code."""
        return answer

    def simulate_answer(self, human_readable=True):
        "Simulates a valid answer for debugging purposes"
        return {"answer": randint(0, 100), "comment": random_string()}

    @classmethod
    def example(cls):
        return cls(
            question_name="age",
            question_text="How old are you in years?",
            min_value=0,
            max_value=10,
        )


if __name__ == "__main__":
    # from edsl.agents import Agent

    q = QuestionNumerical(
        question_name="sadness_scale",
        question_text="On a scale of 1-10 how often do you feel sad or down ?",
        min_value=0,
        max_value=10,
    )
    # results = sadness_scale.by(Agent(traits={"sadness": "Very, very low"})).run()
    # print(results)
