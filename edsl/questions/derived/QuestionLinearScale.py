from __future__ import annotations
from typing import Optional
from edsl.questions.descriptors import QuestionOptionsDescriptor, OptionLabelDescriptor
from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice


class QuestionLinearScale(QuestionMultipleChoice):
    """
    QuestionLinearScale is a question where the user is asked to select a value from a linear scale.
    - `question_options` is a list of successive positive integers
    - `question_labels` are the labels associated with the question options. If provided, there have to be labels for the first and last options.

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
        instructions: Optional[str] = None,
        option_labels: Optional[dict[int, str]] = None,
    ):
        super().__init__(
            question_text=question_text,
            question_options=question_options,
            question_name=question_name,
            short_names_dict=short_names_dict,
            instructions=instructions,
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
    q.instructions
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
    q.from_dict(q.to_dict()) == q
