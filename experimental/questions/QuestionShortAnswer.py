import textwrap
from pydantic import BaseModel, Field, field_validator
from typing import Type, Optional
from edsl.questions.Question import Question
from edsl.questions.schemas import QuestionData, AnswerData
from edsl.questions.settings import Settings
from edsl.utilities.utilities import random_string


class QuestionShortAnswer(QuestionData):
    """Pydantic data model for QuestionShortAnswer"""

    question_text: str = Field(
        ..., min_length=1, max_length=Settings.MAX_QUESTION_LENGTH
    )
    expression_constraint: Optional[str] = Field(
        ..., min_length=0, max_length=Settings.MAX_EXPRESSION_CONSTRAINT_LENGTH
    )
    allow_nonresponse: bool = None

    def __new__(cls, *args, **kwargs):
        # this runs before __init__
        # we create an instance of the Pydantic data model
        instance = super(QuestionShortAnswer, cls).__new__(cls)
        # we run it through __init__, which will run the validators
        instance.__init__(*args, **kwargs)
        # we pass the validated the instance to create a QuestionMultipleChoiceEnhanced
        # which has all the abstract base clas methods we need
        return QuestionShortAnswerEnhanced(instance)

    def __init__(self, **data):
        super().__init__(**data)


class QuestionShortAnswerEnhanced(Question):
    question_type = "short_answer"

    def __init__(self, question: BaseModel):
        super().__init__(question)

    @property
    def instructions(self):
        return textwrap.dedent(
            """\
        You are being asked the following question: {{question_text}}
        {% if expression_constraint %}
        Your response must satisfy the following constraints:
        {{expression_constraint}}
        {% endif %}
        Return a valid JSON formatted exactly like this: 
        {"answer": "<put your answer here>", "comment": "<put explanation here>"}         
        """
        )

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

        return LocalAnswerDataModel

    def simulate_answer(self):
        "Simulates a valid answer for debugging purposes (what the validator expects)"
        return {"answer": random_string()}

    def form_elements(self):
        raise NotImplementedError


if __name__ == "__main__":
    q = QuestionShortAnswer(
        question_text="What do you want to do today?",
        expression_constraint=None,
        question_name="today",
    )
    results = q.run()
    print(results)
