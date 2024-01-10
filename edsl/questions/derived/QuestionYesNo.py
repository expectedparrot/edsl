from typing import Type
from edsl.exceptions import (
    QuestionCreationValidationError,
    QuestionAnswerValidationError,
)
from edsl.questions import Settings, QuestionData, AnswerData
from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice

from edsl.questions.descriptors import QuestionOptionsDescriptor


class QuestionYesNo(QuestionMultipleChoice):
    """Same as a QuestionCheckBox, but with question_options=["yes","no"]"""

    question_type = "yes_no"
    question_options = QuestionOptionsDescriptor(num_choices=2)

    def __init__(
        self,
        question_name: str,
        question_text: str,
        short_names_dict: dict[str, str] = None,
        question_options: list[str] = ["Yes", "No"],
        instructions: str = None,
    ):
        super().__init__(
            question_name=question_name,
            question_text=question_text,
            question_options=question_options,
            short_names_dict=short_names_dict,
            instructions=instructions,
        )
        self.question_options = question_options
