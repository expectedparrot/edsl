import textwrap
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Type
from edsl.exceptions import QuestionAnswerValidationError
from edsl.questions import Question, QuestionData, AnswerData, Settings
from edsl.utilities.utilities import random_string


class QuestionFreeText(QuestionData):
    """Pydantic data model for QuestionFreeText"""

    allow_nonresponse: Optional[bool] = False

    def __new__(cls, *args, **kwargs) -> "QuestionFreeTextEnhanced":
        # runs before __init__
        #   create an instance of QuestionFreeText using the __new__ method from QuestionData
        instance = super(QuestionFreeText, cls).__new__(cls)
        #   call QuestionFreeText's __init__
        #   (Note: Python will not __init__ again after __new__)
        instance.__init__(*args, **kwargs)
        #   pass the validated QuestionFreeText to create a QuestionFreeTextEnhanced
        return QuestionFreeTextEnhanced(instance)

    def __init__(self, **data):
        # call QuestionData's __init__ to run its validators
        super().__init__(**data)


class QuestionFreeTextEnhanced(Question):
    question_type = "free_text"

    def __init__(self, question: QuestionFreeText):
        super().__init__(question)

    @property
    def instructions(self) -> str:
        return textwrap.dedent(
            """\
        You are being asked the following question: {{question_text}}
        Return a valid JSON formatted like this: 
        {"answer": "<put free text answer here>"}
        """
        )

    def translate_answer_code_to_answer(self, answer, scenario):
        """There is no answer code."""
        return answer

    def construct_answer_data_model(self) -> Type[BaseModel]:
        class QuestionFreeTextAnswerDataModel(AnswerData):
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
                    raise QuestionAnswerValidationError(
                        "Empty answer to a `QuestionFreeText` question, but it was not allowed."
                    )
                return value

        return QuestionFreeTextAnswerDataModel

    ################
    # Less important
    ################

    def simulate_answer(self) -> dict[str, str]:
        return {"answer": random_string()}

    def form_elements(self) -> str:
        html_output = f"""
        <label for="{self.question_name}">{self.question_text}</label>
        <div id="{self.question_name}_div">
            <input type="text" id="{self.question_name}" name="{self.question_text}">
        </div>
        """
        return html_output


# if __name__ == 'main':
#     from edsl.questions import QuestionFreeText
#     q = QuestionFreeText(question_text = "How old are you?", question_name = "age")
#     result = q.run()
#     print(result)
