import keyword
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional
from edsl.exceptions import QuestionCreationValidationError
from edsl.questions.settings import Settings
from edsl.utilities.utilities import random_string


class QuestionData(BaseModel):
    """
    Pydantic model that all question-specific question pydantic models inherit from.
    Used to put commonly used validators in one place.
    """

    question_name: Optional[str] = Field(
        None, min_length=1, max_length=Settings.MAX_QUESTION_LENGTH
    )

    short_names_dict: Optional[dict[str, str]] = Field(default_factory=dict)

    question_text: str = Field(
        ..., min_length=1, max_length=Settings.MAX_QUESTION_LENGTH
    )

    @field_validator("question_name")
    def check_name(cls, value):
        return cls.base_validator_check_question_name(value)

    # forbid attributes not defined in the model
    # accept attributes with types that the model doesn't know how to validate
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    # Place commonly used validators below
    def base_validator_check_option_string_lengths(value: list[str]) -> list[str]:
        """Check that each option string is not too long."""
        limit = Settings.MAX_OPTION_LENGTH
        for option in value:
            length = len(option)
            if length > limit:
                raise QuestionCreationValidationError(
                    f"Option {option} is too long ({length} chars, limit={limit} chars)"
                )
            elif length == 0:
                raise QuestionCreationValidationError(
                    f"Option {option} cannot be empty."
                )
        return value

    def base_validator_check_question_name(value: Optional[str]) -> str:
        """Check that question_name is a valid Python identifier and not a Python keyword."""
        # if value is None, generate a random string
        if value is None:
            value = random_string()
        # check that the Question name is a valid Python identifier
        if not value.isidentifier():
            raise QuestionCreationValidationError(
                f"`question_name` must be a valid identifier, but you passed in {value}"
            )
        # check that the Question name is not a Python keyword
        if value in keyword.kwlist:
            raise QuestionCreationValidationError(
                f"`question_name` cannot be a Python keyword, but you passed in {value}"
            )
        return value

    def base_validator_check_unique(value: list[str]) -> list[str]:
        """Check that all elements in a list are unique."""
        if len(value) != len(set(value)):
            raise QuestionCreationValidationError(
                f"Elements must be unique, but you passed in {value}"
            )
        return value


class AnswerData(BaseModel):
    """
    Pydantic model that all question-specific answer pydantic models inherit from.
    Used to put commonly used validators in one place.
    """

    # Place commonly used validators below
    # def base_validator_lte(value, max_value: int) -> int:
    #     """Check that value is less than or equal to max_value."""
    #     if value > max_value:
    #         raise ValueError(f"Value {value} is greater than {max_value}")
    #     return value
