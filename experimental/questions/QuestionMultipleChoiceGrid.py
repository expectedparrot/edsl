import random
import textwrap
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Type, Union
from edsl.questions.Question import Question
from edsl.questions.schemas import QuestionData, AnswerData
from edsl.questions.settings import Settings
from edsl.utilities.utilities import random_string


class QuestionMultipleChoiceGrid(Question):
    """This is a question where the answer is a matrix.
    It looks like this:

            | Yuk   | Yum   |
    --------+-------+-------+
    Hot Dog |   X   |       |
    --------+-------+-------+
    Pizza   |       |   X   |
    --------+-------+-------+

    There are 2 types of matrix questions (Google Forms as example):
    - Checkbox grid: any number of column selections per row allowed
    - Multiple choice grid: only 1 column selection per row allowed

    You have to select one option from each row and column if answer required.
    Otherwise, you can leave a row blank.
    """

    question_type = "multiple_choice_grid"

    @property
    def instructions(self):
        return textwrap.dedent(
            """\
        You are being asked the following multiple choice question in the form of a matrix: 
        {{question_text}}
        The matrix rows are 
        {% for option in row_options %}
        {{ loop.index0 }}: {{option}}
        {% endfor %}                       
        The matrix columns are 
        {% for option in column_options %}
        {{ loop.index0 }}: {{option}}
        {% endfor %}   
        {% if required == True %}
        You are required to provide an answer.
        {% endif %}     
        Return a valid JSON formatted like this using the numbers of the options: 
        {"answer": <[put list of each column option selected for each row here]>, 
        "comment": "<put explanation here>"}
        Example answer: [1,2]
        """
        )

    def translate_answer_code_to_answer(self, answer_codes):
        """Translates the answer codes to the actual answers.
        For example, for a budget question with options ["a", "b", "c"],
        the answer codes are 0, 1, and 2. The LLM will respond with 0.
        This code will translate that to "a".
        """
        translated_codes = []
        for answer_code_list in answer_codes:
            translated_answer_code_list = []
            for answer_code in answer_code_list:
                translated_answer_code_list.append(
                    self.column_options[int(answer_code)]
                )
            translated_codes.append(translated_answer_code_list)

        return translated_codes

    @classmethod
    def construct_question_data_model(cls) -> Type[BaseModel]:
        class LocalQuestionData(QuestionData):
            """Pydantic data model for QuestionMultipleChoiceGrid"""

            question_text: str = Field(
                ..., min_length=1, max_length=Settings.MAX_QUESTION_LENGTH
            )
            row_options: list[str] = Field(
                ..., min_length=1, max_length=Settings.MAX_NUM_OPTIONS
            )
            column_options: list[str] = Field(
                ..., min_length=1, max_length=Settings.MAX_NUM_OPTIONS
            )
            required: bool = False

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

        return LocalQuestionData

    def construct_answer_data_model(self) -> Type[BaseModel]:
        row_options = self.row_options
        column_options = self.column_options
        required = self.required

        class LocalAnswerDataModel(AnswerData):
            answer: list[Union[int, None]]

            @model_validator(mode="after")
            def check_required_answer(self):
                if required == True and len(self.answer) < len(row_options):
                    raise ValueError("There are missing answers.")
                return self

            @model_validator(mode="after")
            def check_answer_count(self):
                if len(self.answer) > len(row_options):
                    raise ValueError("There are too many answers.")
                return self

        return LocalAnswerDataModel

    def simulate_answer(self):
        # Expand to allow multiple selections for checkbox (non-mc) case
        "Simulates a valid answer for debugging purposes (what the validator expects)"
        answers = []
        for _ in self.row_options:
            answers.append([random.choice(range(len(self.column_options)))])
        return {"answer": answers, "comment": random_string()}


if __name__ == "__main__":
    from edsl.exceptions import (
        QuestionResponseValidationError,
        QuestionAnswerValidationError,
    )

    print("Now validating multiple choice grid questions")

    q = QuestionMultipleChoiceGrid(
        question_text="Indicate how much you like the following foods.",
        row_options=["Pizza", "Ice Cream"],
        column_options=["Very much", "Somewhat", "Not at all", "Don't know"],
        required=True,
    )
    print(q.get_prompt())
    response = {"answer": [0, 1], "comment": "OK"}
    print(response)
    q.validate_response(response)
    response.pop("comment")
    q.validate_answer(response)
    print("This is a valid response.\n")

    print("Now checking a non-required question.")
    q = QuestionMultipleChoiceGrid(
        question_text="Indicate how much you like the following foods.",
        row_options=["Pizza", "Ice Cream"],
        column_options=["Very much", "Somewhat", "Not at all", "Don't know"],
        required=False,
    )
    print(q.get_prompt())
    response = {"answer": [None, 2], "comment": "OK"}
    print(response)
    q.validate_response(response)
    response.pop("comment")
    q.validate_answer(response)
    print("This is a valid response.\n")

    print("Now checking a required question.")
    q = QuestionMultipleChoiceGrid(
        question_text="Indicate how much you like the following foods.",
        row_options=["Pizza", "Ice Cream"],
        column_options=["Very much", "Somewhat", "Not at all", "Don't know"],
        required=True,
    )
    print(q.get_prompt())
    try:
        response = {"answer": [3, None], "comment": "OK"}
        print(response)
        q.validate_response(response)
        response.pop("comment")
        q.validate_answer(response)
    except QuestionAnswerValidationError:
        print("Caught bad answer.\n")

    print(q.get_prompt())
    try:
        response = {"answer": [["Mon"], ["Wed"]], "comment": "OK"}
        print(response)
        q.validate_response(response)
        response.pop("comment")
        q.validate_answer(response)
    except QuestionAnswerValidationError:
        print("Caught bad answer.\n")
