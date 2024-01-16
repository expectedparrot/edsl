from __future__ import annotations
from typing import Optional
from edsl.exceptions import QuestionCreationValidationError
from edsl.questions.QuestionCheckBox import QuestionCheckBox


class QuestionTopK(QuestionCheckBox):
    """
    This question asks the user to select exactly K options from a list.

    Arguments:
    - `question_name` is the name of the question (string)
    - `question_text` is the text of the question (string)
    - `question_options` are the options the user should select from (list of strings)
    - `min_selections` is the minimum number of options that must be selected (positive integer).
    - `max_selections` is the maximum number of options that must be selected (positive integer). Must be equal to `min_selections`

    Optional arguments:
    - `instructions` are the instructions for the question (string). If not provided, the default instructions are used. To view them, run `QuestionTopK.default_instructions`
    - `short_names_dict` maps question_options to short names (dictionary mapping strings to strings)

    For an example, run `QuestionTopK.example()`
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
        return cls(
            question_name="two_fruits",
            question_text="Which of the following fruits do you prefer?",
            question_options=["apple", "banana", "carrot", "durian"],
            min_selections=2,
            max_selections=2,
        )


def main():
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
