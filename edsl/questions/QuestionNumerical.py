import re
import textwrap
from random import randint
from pydantic import BaseModel, field_validator
from typing import Type, Union
from edsl.questions import Question, QuestionData, AnswerData
from edsl.exceptions import QuestionAnswerValidationError
from edsl.utilities.utilities import random_string


from edsl.utilities.utilities import random_string


class QuestionNumerical(QuestionData):
    """Pydantic data model for QuestionNumerical"""

    min_value: Union[int, float, None] = None
    max_value: Union[int, float, None] = None

    # see QuestionFreeText for an explanation of how __new__ works
    def __new__(cls, *args, **kwargs) -> "QuestionNumericalEnhanced":
        instance = super(QuestionNumerical, cls).__new__(cls)
        instance.__init__(*args, **kwargs)
        return QuestionNumericalEnhanced(instance)


class QuestionNumericalEnhanced(Question):
    question_type = "numerical"

    def __init__(self, question: BaseModel):
        super().__init__(question)

    @property
    def instructions(self) -> str:
        # make the min/max conditional parts of the instructions {% if ... end if}
        return textwrap.dedent(
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
        """
        Simpler default prompt that works with GPT-4:

        You are being asked the following question: {{question_text}}
        {% if min_value is not none %}
        Minimum answer value: {{min_value}}
        {% endif %}
        {% if max_value is not none %}
        Maximum answer value: {{max_value}}
        {% endif %}
        Return a valid JSON formatted like this: 
        {"answer": "<put integer or float answer here>", "comment": "<put explanation here>"}
        """

    def construct_answer_data_model(self) -> Type[BaseModel]:
        class QuestionNumericalAnswerDataModel(AnswerData):
            answer: Union[int, float, str]

            @field_validator("answer")
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

            @field_validator("answer")
            def check_answer(cls, value):
                # breakpoint()
                if self.min_value is not None and value < self.min_value:
                    raise QuestionAnswerValidationError(
                        f"Value {value} is less than {self.min_value}"
                    )
                if self.max_value is not None and value > self.max_value:
                    raise QuestionAnswerValidationError(
                        f"Value {value} is greater than {self.max_value}"
                    )
                return value

        return QuestionNumericalAnswerDataModel

    ################
    # Less important
    ################

    def translate_answer_code_to_answer(self, answer, scenario=None):
        """There is no answer code."""
        return answer

    def simulate_answer(self, human_readable=True):
        "Simulates a valid answer for debugging purposes"
        return {"answer": randint(0, 100), "comment": random_string()}

    def form_elements(self):
        html_output = f"\n\n\n<label>{self.question_text}</label>\n"
        html_output += f"""<div id="{self.question_name}_div">
        <input type="number" id="{self.question_name}" name="{self.question_text}">
        </div>\n"""
        return html_output


if __name__ == "__main__":
    from edsl.agents import Agent

    sadness_scale = QuestionNumerical(
        question_name="sadness_scale",
        question_text="On a scale of 1-10 how often do you feel sad or down ?",
        min_value=0,
        max_value=10,
    )
    results = sadness_scale.by(Agent(traits={"sadness": "Very, very low"})).run()
    print(results)
