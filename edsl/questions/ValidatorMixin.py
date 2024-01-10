from typing import Union
from edsl.exceptions import (
    QuestionAnswerValidationError,
)


class ValidatorMixin:
    def validate_answer_basic(self, answer: dict[str, Union[str, int]]) -> None:
        """Checks that the answer is a dictionary with an answer key"""
        if not isinstance(answer, dict):
            raise QuestionAnswerValidationError(
                f"Answer must be a dictionary (got {answer})."
            )
        if not "answer" in answer:
            raise QuestionAnswerValidationError(
                f"Answer must have an 'answer' key (got {answer})."
            )

    def validate_answer_multiple_choice(
        self, answer: dict[str, Union[str, int]]
    ) -> None:
        """Checks that answer["answer"] is a valid answer code for a multiple choice question"""
        try:
            answer_code = int(answer["answer"])
        except:
            raise QuestionAnswerValidationError(
                f"Answer code must be a string, a bytes-like object or a real number (got {answer['answer']})."
            )
        if not answer_code >= 0:
            raise QuestionAnswerValidationError(
                f"Answer code must be a non-negative integer (got {answer_code})."
            )
        if int(answer_code) not in range(len(self.question_options)):
            raise QuestionAnswerValidationError(
                f"Answer code {answer_code} must be in {list(range(len(self.question_options)))}."
            )
