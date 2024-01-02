from typing import Type, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
from edsl.exceptions import (
    QuestionAnswerValidationError,
    QuestionCreationValidationError,
)
from edsl.questions import Settings, QuestionData, AnswerData
from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoiceEnhanced


class QuestionLinearScale(QuestionData):
    """Pydantic data model for QuestionLinearScale"""

    question_text: str = Field(
        ..., min_length=1, max_length=Settings.MAX_QUESTION_LENGTH
    )
    question_options: list[int]
    option_labels: Optional[dict[int, str]] = None

    # see QuestionFreeText for an explanation of how __new__ works
    def __new__(cls, *args, **kwargs) -> "QuestionLinearScaleEnhanced":
        instance = super(QuestionLinearScale, cls).__new__(cls)
        instance.__init__(*args, **kwargs)
        return QuestionLinearScaleEnhanced(instance)

    @field_validator("question_options")
    def check_successive(cls, value):
        if sorted(value) != list(range(min(value), max(value) + 1)):
            raise QuestionCreationValidationError(
                f"LinearScale.question_options must be a list of successive integers, e.g. [1, 2, 3]"
            )
        return value

    @model_validator(mode="after")
    def check_option_labels(self, value):
        if self.option_labels is not None:
            if min(self.option_labels.keys()) != min(self.question_options):
                raise QuestionCreationValidationError(f"First option needs a label")
            if max(self.option_labels.keys()) != max(self.question_options):
                raise QuestionCreationValidationError(f"Last option needs a label")
        return self


class QuestionLinearScaleEnhanced(QuestionMultipleChoiceEnhanced):
    """
    Inherits from QuestionMultipleChoice, because the two are similar.
    - A difference is that the answers must have an ordering.
    - Not every option has to have a label.
    - But if option labels are provided, there have to be labels for the first and last options.
    """

    question_type = "linear_scale"

    def __init__(self, question: BaseModel):
        super().__init__(question)

    def construct_answer_data_model(self) -> Type[BaseModel]:
        "Constructs the answer data model for this question"
        acceptable_values = self.question_options

        class QuestionLinearScaleAnswerDataModel(AnswerData):
            answer: int

            @field_validator("answer")
            def check_answer(cls, value):
                if value in acceptable_values:
                    return value
                else:
                    raise QuestionAnswerValidationError(
                        f"Answer {value} is not in the acceptable values {acceptable_values}"
                    )

        return QuestionLinearScaleAnswerDataModel

    def form_elements(self) -> str:
        html_output = f"\n\n\n<label>{self.question_text}</label>\n"
        for index in range(1, 6):  # assuming the scale is from 1 to 5
            html_output += f"""<div id = "{self.question_name}_div_{index}">
            <input type="radio" id="{self.question_name}_{index}" name="{self.question_name}" value="{index}">
            <label for="{self.question_name}_{index}">{index}</label>
            </div>\n"""
        return html_output
