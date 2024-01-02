from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Type, Union

from edsl.questions.Question import Question
from edsl.questions.schemas import QuestionData, AnswerData
from edsl.questions.settings import Settings


class QuestionMatrix(Question):
    question_type = "matrix"

    """This is a question where the answer is a matrix.
    It looks like this:

            | Yuk   | Yum   |
    --------+-------+-------+
    Hot Dog |   X   |       |
    --------+-------+-------+
    Pizza   |       |   X   |
    --------+-------+-------+

    You have to select one option from each row and column if answer_required.
    Otherise, you can leave a row blank.
    """

    def construct_question_data_model(self) -> Type[BaseModel]:
        class LocalQuestionData(QuestionData):
            """Pydantic data model for QuestionMatrix"""

            question_text: str = Field(
                ..., min_length=1, max_length=Settings.MAX_QUESTION_LENGTH
            )
            row_options: list[str]
            column_options: list[str]
            answer_required: bool = False

            @field_validator("row_options")
            def check_unique(cls, value):
                return cls.base_validator_check_unique(value)

            @field_validator("row_options")
            def check_option_string_lengths(cls, value):
                return cls.base_validator_check_option_string_lengths(value)

            @field_validator("column_options")
            def check_unique(cls, value):
                return cls.base_validator_check_unique(value)

            @field_validator("column_options")
            def check_option_string_lengths(cls, value):
                return cls.base_validator_check_option_string_lengths(value)

            # raise NotImplementedError("I'm getting tired of these")

        return LocalQuestionData

    def construct_answer_data_model(self) -> Type[BaseModel]:
        class LocalAnswerDataModel(AnswerData):
            answer: list[Union[int, None]]

            @model_validator(mode="after")
            def check_answer(self):
                if self.answer_required:
                    for row in self.answer.keys():
                        for column in self.answer[row].keys():
                            if self.answer[row][column] is None:
                                raise ValueError(
                                    f"Answer required but not provided for {row}, {column}"
                                )
                return self

            # raise NotImplementedError("I'm getting tired of these")

        return LocalAnswerDataModel
