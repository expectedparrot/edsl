from __future__ import annotations
from typing import Optional
from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice


class QuestionLikertFive(QuestionMultipleChoice):
    """
    This question asks the user to respond to a statement on a 5-point Likert scale.

    Arguments:
    - `question_name` is the name of the question (string)
    - `question_text` is the text of the question (string)

    Optional arguments:
    - `instructions` are the instructions for the question (string). If not provided, the default instructions are used. To view them, run `QuestionLikertFive.default_instructions`
    - `question_options` are the options the user should select from (list of strings). If not provided, the default likert options are used. To view them, run `QuestionLikertFive.likert_options`
    - `short_names_dict` maps question_options to short names (dictionary mapping strings to strings)

    For an example, see `QuestionLikertFive.example()`
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
        return cls(
            question_name="happy_raining",
            question_text="I'm only happy when it rains.",
        )


def main():
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
