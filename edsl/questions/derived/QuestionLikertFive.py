"""This question asks the user to respond to a statement on a 5-point Likert scale."""
from __future__ import annotations
from typing import Optional
from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice


class QuestionLikertFive(QuestionMultipleChoice):
    """
    This question asks the respondent to respond to a statement on a 5-point Likert scale.

    :param question_name: The name of the question.
    :type question_name: str
    :param question_text: The text of the question.
    :type question_text: str
    :param question_options: The options the respondent should select from (list of strings). If not provided, the default likert options are used. To view them, run `QuestionLikertFive.likert_options`.
    :type question_options: list[str], optional
    :param instructions: Instructions for the question. If not provided, the default instructions are used. To view them, run `QuestionLikertFive.default_instructions`.
    :type instructions: str, optional
    :param short_names_dict: Maps question_options to short names.
    :type short_names_dict: dict[str, str], optional

    For an example, see `QuestionLikertFive.example()`.
    """

    question_type = "likert_five"
    likert_options: list[str] = [
        "Strongly disagree",
        "Disagree",
        "Neutral",
        "Agree",
        "Strongly agree",
    ]
    # default_instructions = QuestionMultipleChoice.default_instructions

    def __init__(
        self,
        question_name: str,
        question_text: str,
        question_options: Optional[list[str]] = likert_options,
        short_names_dict: Optional[dict[str, str]] = None,
    ):
        """Initialize the question."""
        super().__init__(
            question_name=question_name,
            question_text=question_text,
            question_options=question_options,
            short_names_dict=short_names_dict,
        )

    ################
    # Helpful
    ################
    @classmethod
    def example(cls) -> QuestionLikertFive:
        """Return an example question."""
        return cls(
            question_name="happy_raining",
            question_text="I'm only happy when it rains.",
        )


def main():
    """Test QuestionLikertFive."""
    from edsl.questions.derived.QuestionLikertFive import QuestionLikertFive

    q = QuestionLikertFive.example()
    q.question_text
    q.question_options
    q.question_name
    q.short_names_dict
    # validate an answer
    q.validate_answer({"answer": 0, "comment": "I like custard"})
    # translate answer code
    q.translate_answer_code_to_answer(0, {})
    q.simulate_answer()
    q.simulate_answer(human_readable=False)
    q.validate_answer(q.simulate_answer(human_readable=False))
    # serialization (inherits from Question)
    q.to_dict()
    assert q.from_dict(q.to_dict()) == q
