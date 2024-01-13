import re
import textwrap
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Type
from edsl.questions.experimental.QuestionShortAnswer import QuestionShortAnswer
from edsl.questions.schemas import QuestionData, AnswerData
from edsl.questions.settings import Settings
from edsl.utilities.utilities import random_string


class QuestionShortAnswerText(QuestionShortAnswer):
    question_type: str = "short_answer_text"

    @property
    def instructions(self):
        return textwrap.dedent(
            """\
        You are being asked the following question requiring a text response: 
        {{question_text}}
        {% if expression_constraint %}
        Your answer must satisfy the following constraints (expressed in Python):
        {{expression_constraint}}
        {% endif %}
        Return a valid JSON formatted exactly as follows that satisfies the constraints: 
        {"answer": "<put text answer here>", "comment": "<put explanation here>"}  

        For example, for the question is "What is your job?" with constraints 
        len(answer) < 25 and 'job' not in answer
        the following response would be valid:
        {"answer": "I work as a locksmith", "comment": "My work involves keys and locks."}
        """
        )

    def __repr__(self):
        return f"""{self.__class__.__name__}(question_text = "{self.question_text}", expression_constraints = {self.expression_constraints}, question_name = "{self.question_name}")"""

    @classmethod
    def construct_question_data_model(cls) -> Type[BaseModel]:
        class LocalQuestionData(QuestionData):
            """Pydantic data model for QuestionShortAnswerText"""

            question_text: str = Field(
                ..., min_length=1, max_length=Settings.MAX_QUESTION_LENGTH
            )
            expression_constraint: str = Field(
                ..., min_length=0, max_length=Settings.MAX_EXPRESSION_CONSTRAINT_LENGTH
            )
            allow_nonresponse: Optional[bool] = None

            @field_validator("expression_constraint")
            def check_expression_constraint_logic(cls, value):
                if not re.match(
                    r"^[a-zA-Z0-9_\s\'\.\+\-\*\/\(\)\%\>\<\=\!\&\|\~\^\,\:\;\[\]\{\}]*$",
                    value,
                ):
                    raise Exception(
                        "Expression constraint contains invalid characters."
                    )
                return value

        return LocalQuestionData

    def translate_answer_code_to_answer(self, answer, scenario=None):
        """There is no answer code."""
        return answer

    def construct_answer_data_model(self) -> Type[BaseModel]:
        class LocalAnswerDataModel(AnswerData):
            answer: str = Field(
                ..., min_length=0, max_length=Settings.MAX_ANSWER_LENGTH
            )

            @field_validator("answer")
            def check_answer(cls, value):
                if (
                    hasattr(self, "allow_nonresponse")
                    and self.allow_nonresponse == False
                    and (value == "" or value is None)
                ):
                    raise ValueError("You must provide a response.")
                return value

            @field_validator("answer")
            def check_expression_constraint(cls, value):
                print(value)
                formatted_value = (
                    "'" + value + "'"
                )  # add quotes to make it insertable with quotes
                if not eval(
                    self.expression_constraint.replace("answer", formatted_value)
                ):
                    # if not simple_eval(self.expression_constraint, names={'answer': formatted_value}):
                    raise Exception("Answer does not match expression constraint.")
                return value

        return LocalAnswerDataModel

    def simulate_answer(self):
        "Simulates a valid answer for debugging purposes (what the validator expects)"
        return {"answer": random_string()}

    def form_elements(self):
        raise NotImplementedError


if __name__ == "__main__":
    q = QuestionShortAnswerText(
        question_text="What would you like to be when you grow up?",
        expression_constraint="len(answer) < 50 and 'imagine' in answer",
        question_name="grow_up",
    )
    from edsl import Agent, Scenario, print_dict_with_rich

    a_20yo_finance_student = Agent(
        traits={"age": "20 years old", "occupation": "finance student"}
    )
    print_dict_with_rich(a_20yo_finance_student.answer_question(q))
