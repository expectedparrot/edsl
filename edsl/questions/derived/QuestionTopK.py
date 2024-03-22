"""This module contains the QuestionTopK class. It is a subclass of the QuestionMultipleChoice class and is used to create questions where the respondent is prompted to respond to respond with a list of ranked items from a given list of options.
Example usage:

.. code-block:: python

    from edsl.questions import QuestionTopK

    q = QuestionTopK(
        question_name = "foods_rank", 
        question_text = "Select the best foods.", 
        question_options = ["Pizza", "Pasta", "Salad", "Soup"],
        num_selections = 2
    )

"""
from __future__ import annotations
from typing import Optional
from edsl.exceptions import QuestionCreationValidationError
from edsl.questions.QuestionCheckBox import QuestionCheckBox


class QuestionTopK(QuestionCheckBox):
    """
    This question asks the respondent to select exactly K options from a list.

    :param question_name: The name of the question.
    :type question_name: str
    :param question_text: The text of the question.
    :type question_text: str
    :param question_options: The options the respondent should select from.
    :type question_options: list[str]
    :param instructions: Instructions for the question. If not provided, the default instructions are used. To view them, run `QuestionTopK.default_instructions`.
    :type instructions: str, optional
    :param short_names_dict: Maps question_options to short names.
    :type short_names_dict: dict[str, str], optional
    :param num_selections: The number of options that must be selected.
    :type num_selections: int

    For an example, run `QuestionTopK.example()`.
    """

    question_type = "top_k"

    def __init__(
        self,
        question_name: str,
        question_text: str,
        question_options: list[str],
        min_selections: int,
        max_selections: int,
        short_names_dict: Optional[dict[str, str]] = None,
    ):
        """Initialize the question."""
        super().__init__(
            question_name=question_name,
            question_text=question_text,
            question_options=question_options,
            short_names_dict=short_names_dict,
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
    q.short_names_dict
    # validate an answer
    q.validate_answer({"answer": [0, 3], "comment": "I like custard"})
    # translate answer code
    q.translate_answer_code_to_answer([0, 3], {})
    # simulate answer
    q.simulate_answer()
    q.simulate_answer(human_readable=False)
    q.validate_answer(q.simulate_answer(human_readable=False))
    # serialization (inherits from Question)
    q.to_dict()
    assert q.from_dict(q.to_dict()) == q
