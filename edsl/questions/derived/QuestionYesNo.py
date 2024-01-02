from pydantic import BaseModel, Field, field_validator
from typing import Type
from edsl.exceptions import (
    QuestionCreationValidationError,
    QuestionAnswerValidationError,
)
from edsl.questions import Settings, QuestionData, AnswerData
from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoiceEnhanced


class QuestionYesNo(QuestionData):
    """Pydantic data model for QuestionYesNo"""

    question_text: str = Field(
        ..., min_length=1, max_length=Settings.MAX_QUESTION_LENGTH
    )
    question_options: list = ["Yes", "No"]

    def __new__(cls, *args, **kwargs) -> "QuestionYesNoEnhanced":
        # see QuestionFreeText for an explanation of how __new__ works
        instance = super(QuestionYesNo, cls).__new__(cls)
        instance.__init__(*args, **kwargs)
        return QuestionYesNoEnhanced(instance)

    @field_validator("question_options")
    def check_successive(cls, value):
        if sorted(value) != ["No", "Yes"]:
            raise QuestionCreationValidationError(f"Options must be 'Yes' and 'No'")
        return value


class QuestionYesNoEnhanced(QuestionMultipleChoiceEnhanced):
    """Same as a QuestionCheckBox, but with question_options=["yes","no"]"""

    question_type = "yes_no"

    def __init__(self, question: BaseModel):
        super().__init__(question)

    def construct_answer_data_model(self) -> Type[BaseModel]:
        acceptable_values = list(range(len(self.question_options)))

        class QuestionYesNoAnswerDataModel(AnswerData):
            answer: int

            @field_validator("answer")
            def check_answer(cls, value):
                if value in acceptable_values:
                    return value
                else:
                    raise QuestionAnswerValidationError(
                        f"Answer {value} is not in the acceptable values {acceptable_values}"
                    )

        return QuestionYesNoAnswerDataModel
