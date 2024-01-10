from typing import Type
from edsl.questions import Settings
from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice


class QuestionLikertFive(QuestionMultipleChoice):
    """QuestionLikertFive"""

    question_type = "likert_five"

    likert_options: list[str] = [
        "Strongly disagree",
        "Disagree",
        "Neutral",
        "Agree",
        "Strongly agree",
    ]

    def __init__(
        self,
        question_name: str,
        question_text: str,
        question_options: list[str] = likert_options,
        short_names_dict: dict[str, str] = None,
        instructions: str = None,
    ):
        super().__init__(
            question_name=question_name,
            question_text=question_text,
            question_options=question_options,
            short_names_dict=short_names_dict,
            instructions=instructions,
        )
