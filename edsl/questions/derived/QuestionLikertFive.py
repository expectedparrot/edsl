from __future__ import annotations
from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice


class QuestionLikertFive(QuestionMultipleChoice):
    """
    QuestionLikertFive is a question the user is asked to answer on 5-point Likert scale.
    - `question_options` is a list of strings ["Strongly disagree", "Disagree", "Neutral", "Agree", "Strongly agree"]

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
    q.instructions
    # validate an answer
    q.validate_answer({"answer": 0, "comment": "I like custard"})
    # translate answer code
    q.translate_answer_code_to_answer(0, {})
    q.simulate_answer()
    q.simulate_answer(human_readable=False)
    q.validate_answer(q.simulate_answer(human_readable=False))
    # serialization (inherits from Question)
    q.to_dict()
    q.from_dict(q.to_dict()) == q
