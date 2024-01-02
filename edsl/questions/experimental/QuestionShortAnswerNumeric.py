import textwrap
from pydantic import BaseModel, Field, field_validator
from simpleeval import simple_eval  # type: ignore
from typing import Optional, Type
from edsl.questions.experimental.QuestionShortAnswer import QuestionShortAnswer
from edsl.questions.schemas import QuestionData, AnswerData
from edsl.questions.settings import Settings
from edsl.utilities.utilities import random_string


class QuestionShortAnswerNumeric(QuestionShortAnswer):
    question_type: str = "short_answer_numeric"

    @property
    def instructions(self):
        return textwrap.dedent(
            """\
        You are being asked the following question requiring a numeric response: 
        {{question_text}}
        {% if expression_constraint %}
        Your response must be numeric and satisfy the following constraints:
        {{expression_constraint}}
        {% endif %}
        Return a valid JSON formatted exactly like this: 
        {"answer": "<put numeric answer here>", "comment": "<put explanation here>"}  
        Example of a correctly formatted response:
        {"answer": "100", "comment": "This is my explanation..."}          
        """
        )

    def __repr__(self):
        return f"""{self.__class__.__name__}(question_text = "{self.question_text}", expression_constraints = {self.expression_constraints}, question_name = "{self.question_name}")"""

    @classmethod
    def construct_question_data_model(cls) -> Type[BaseModel]:
        class LocalQuestionData(QuestionData):
            """Pydantic data model for QuestionShortAnswerNumeric"""

            question_text: str = Field(
                ..., min_length=1, max_length=Settings.MAX_QUESTION_LENGTH
            )
            expression_constraint: str = Field(
                ..., min_length=0, max_length=Settings.MAX_EXPRESSION_CONSTRAINT_LENGTH
            )
            allow_nonresponse: Optional[bool] = None

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
            def check_answer_numeric(cls, value):
                if not value.isnumeric():
                    raise ValueError(f"Answer should be numeric.")
                return value

            @field_validator("answer")
            def check_expression_constraint(cls, value):
                numeric_value = int(value) if value.isdigit() else float(value)
                if not simple_eval(
                    self.expression_constraint, names={"answer": numeric_value}
                ):
                    raise Exception("Answer does not match expression constraint.")
                return value

        return LocalAnswerDataModel

    def simulate_answer(self):
        "Simulates a valid answer for debugging purposes (what the validator expects)"
        return {"answer": random_string()}

    def form_elements(self):
        raise NotImplementedError


if __name__ == "__main__":
    q = QuestionShortAnswerNumeric(
        question_text="How many astronauts do you think there are in the world right now?",
        expression_constraint="answer > 0",
        question_name="astronauts",
    )

    from edsl import Agent

    a_nasa_engineer = Agent(traits={"occupation": """NASA engineer"""})
    a_fashion_model = Agent(traits={"occupation": """fashion model"""})
