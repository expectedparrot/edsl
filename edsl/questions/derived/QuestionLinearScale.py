from __future__ import annotations
import textwrap
from typing import Optional
from edsl.questions.descriptors import QuestionOptionsDescriptor, OptionLabelDescriptor
from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice


class QuestionLinearScale(QuestionMultipleChoice):
    """
    This question asks the user to respond to a statement on a linear scale.

    Arguments:
    - `question_name` is the name of the question (string)
    - `question_text` is the text of the question (string)
    - `question_options` are the options the user should select from (list of integers)

    Optional arguments:
    - `instructions` are the instructions for the question (string). If not provided, the default instructions are used. To view them, run `QuestionLinearScale.default_instructions`
    - `option_labels` maps question_options to labels (dictionary mapping integers to strings)
    - `short_names_dict` maps question_options to short names (dictionary mapping strings to strings)

    For an example, see `QuestionLinearScale.example()`
    """

    question_type = "linear_scale"
    option_labels: Optional[dict[int, str]] = OptionLabelDescriptor()
    question_options = QuestionOptionsDescriptor(linear_scale=True)

    def __init__(
        self,
        question_text: str,
        question_options: list[int],
        question_name: str,
        short_names_dict: Optional[dict[str, str]] = None,
        option_labels: Optional[dict[int, str]] = None,
    ):
        super().__init__(
            question_text=question_text,
            question_options=question_options,
            question_name=question_name,
            short_names_dict=short_names_dict,
        )
        self.question_options = question_options
        self.option_labels = option_labels

    ################
    # Helpful
    ################
    @classmethod
    def example(cls) -> QuestionLinearScale:
        return cls(
            question_text="How much do you like ice cream?",
            question_options=[1, 2, 3, 4, 5],
            question_name="ice_cream",
            option_labels={1: "I hate it", 5: "I love it"},
        )


def main():
    from edsl.questions.derived.QuestionLinearScale import QuestionLinearScale

    q = QuestionLinearScale.example()
    q.question_text
    q.question_options
    q.question_name
    q.short_names_dict
    # validate an answer
    q.validate_answer({"answer": 3, "comment": "I like custard"})
    # translate answer code
    q.translate_answer_code_to_answer(3, {})
    # simulate answer
    q.simulate_answer()
    q.simulate_answer(human_readable=False)
    q.validate_answer(q.simulate_answer(human_readable=False))
    # serialization (inherits from Question)
    q.to_dict()
    assert q.from_dict(q.to_dict()) == q
