from __future__ import annotations
from typing import Optional

from edsl.exceptions import QuestionCreationValidationError
from edsl.questions.QuestionCheckBox import QuestionCheckBox


class QuestionTopK(QuestionCheckBox):
    """This question prompts the agent to select exactly K options from a list."""

    question_type = "top_k"

    def __init__(
        self,
        question_name: str,
        question_text: str,
        question_options: list[str],
        min_selections: int,
        max_selections: int,
    ):
        """Initialize the question.

        :param question_name: The name of the question.
        :param question_text: The text of the question.
        :param question_options: The options the respondent should select from.
        :param instructions: Instructions for the question. If not provided, the default instructions are used. To view them, run `QuestionTopK.default_instructions`.
        :param num_selections: The number of options that must be selected.
        """
        super().__init__(
            question_name=question_name,
            question_text=question_text,
            question_options=question_options,
            min_selections=min_selections,
            max_selections=max_selections,
        )
        if min_selections != max_selections:
            raise QuestionCreationValidationError(
                "TopK questions must have min_selections == max_selections"
            )
        if min_selections < 1:
            raise QuestionCreationValidationError(
                "TopK questions must have min_selections > 0"
            )

    ################
    # Helpful
    ################
    @classmethod
    def example(cls) -> QuestionTopK:
        """Return an example question."""
        return cls(
            question_name="two_fruits",
            question_text="Which of the following fruits do you prefer?",
            question_options=["apple", "banana", "carrot", "durian"],
            min_selections=2,
            max_selections=2,
        )


def main():
    """Test QuestionTopK."""
    from edsl.questions.derived.QuestionTopK import QuestionTopK

    q = QuestionTopK.example()
    q.question_text
    q.question_options
    q.question_name
    # validate an answer
    q._validate_answer({"answer": [0, 3], "comment": "I like custard"})
    # translate answer code
    q._translate_answer_code_to_answer([0, 3], {})
    # simulate answer
    q._simulate_answer()
    q._simulate_answer(human_readable=False)
    q._validate_answer(q._simulate_answer(human_readable=False))
    # serialization (inherits from Question)
    q.to_dict()
    assert q.from_dict(q.to_dict()) == q

    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
