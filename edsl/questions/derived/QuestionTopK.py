from pydantic import BaseModel, Field, model_validator, field_validator
from typing import Type
from edsl.exceptions import QuestionCreationValidationError
from edsl.questions import QuestionData, Settings
from edsl.questions.QuestionCheckBox import QuestionCheckBoxEnhanced


class QuestionTopK(QuestionData):
    """Pydantic data model for QuestionTopK"""

    question_text: str = Field(
        ..., min_length=1, max_length=Settings.MAX_QUESTION_LENGTH
    )
    question_options: list[str] = Field(
        ...,
        min_length=Settings.MIN_NUM_OPTIONS,
        max_length=Settings.MAX_NUM_OPTIONS,
    )
    min_selections: int
    max_selections: int

    # see QuestionFreeText for an explanation of how __new__ works
    def __new__(cls, *args, **kwargs):
        instance = super(QuestionTopK, cls).__new__(cls)
        instance.__init__(*args, **kwargs)
        return QuestionTopKEnhanced(instance)

    @field_validator("question_options")
    def check_unique(cls, value):
        return cls.base_validator_check_unique(value)

    @field_validator("question_options")
    def check_option_string_lengths(cls, value):
        return cls.base_validator_check_option_string_lengths(value)

    @model_validator(mode="after")
    def check_equal_min_max(self, value):
        if self.min_selections != self.max_selections:
            raise QuestionCreationValidationError(
                f"TopK question must have equal min and max selections"
            )
        return self

    @model_validator(mode="after")
    def check_min_within_bounds(self, value):
        if self.min_selections > len(self.question_options):
            raise QuestionCreationValidationError(
                f"TopK question must have min selections less than or equal to the number of options"
            )
        if self.min_selections <= 0:
            raise QuestionCreationValidationError(
                f"TopK question must have min selections greater than 0"
            )
        return self


class QuestionTopKEnhanced(QuestionCheckBoxEnhanced):
    """
    Same as a CheckBox question except required selections count is fixed.
    """

    question_type = "top_k"

    def __init__(self, question: BaseModel):
        # Set the required number of option selections
        min_selections: int
        max_selections: int

        super().__init__(question)

    def construct_answer_data_model(self) -> Type[BaseModel]:
        return super().construct_answer_data_model()
