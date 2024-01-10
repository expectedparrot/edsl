from typing import Type, Optional
from edsl.exceptions import (
    QuestionAnswerValidationError,
    QuestionCreationValidationError,
)
from edsl.questions import Settings, Question
from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice

from edsl.questions.descriptors import QuestionOptionsDescriptor, OptionLabelDescriptor


class QuestionLinearScale(QuestionMultipleChoice):
    question_type = "linear_scale"
    """QuestionLinearScale
    
    Inherits from QuestionMultipleChoice, because the two are similar.
    - A difference is that the answers must have an ordering.
    - Not every option has to have a label.
    - But if option labels are provided, there have to be labels for the first and last options.
    """

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
        # self.instructions = instructions or self.default_instructions
        self.question_options = question_options  # note this uses the LinearScale descriptor, not the one from MC
        self.option_labels = option_labels

    def validate_answer(self, answer_raw):
        value = answer_raw["answer"]
        if value is None:
            raise QuestionAnswerValidationError("Answer cannot be None.")
        if type(value) != int:
            raise QuestionAnswerValidationError(f"Answer {value} is not an integer.")
        acceptable_values = set(range(len(self.question_options)))
        if value not in acceptable_values:
            raise QuestionAnswerValidationError(
                f"Answer {value} is not in the acceptable values {acceptable_values}"
            )
        return answer_raw

    @classmethod
    def example(cls):
        return cls(
            question_text="How much do you like ice cream?",
            question_options=[1, -2, 3, 4, 5],
            question_name="ice_cream",
            option_labels={1: "I hate it", 5: "I love it"},
        )


if __name__ == "__main__":
    # q = QuestionLinearScale.example()

    q = QuestionLinearScale.from_dict(
        {
            "question_text": "On a scale from 1 to 5, how much do you like pizza?",
            "question_options": [1, -2, 3, 4, 5],
            "question_name": "pizza",
            "option_labels": None,
            "question_type": "linear_scale",
            "short_names_dict": {},
        }
    )

    # class Dummy:
    #     d = QuestionOptionsDescriptor(linear_scale=True)

    #     def __init__(self):
    #         self.d = [1, -2, 3]

    # dummy = Dummy()
