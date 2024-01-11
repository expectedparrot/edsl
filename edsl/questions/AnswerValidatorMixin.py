from typing import Union
from edsl.exceptions import (
    QuestionAnswerValidationError,
)


class AnswerValidatorMixin:
    def validate_answer_template_basic(
        self, answer: dict[str, Union[str, int]]
    ) -> None:
        """Checks that the answer is a dictionary with an answer key"""
        if not isinstance(answer, dict):
            raise QuestionAnswerValidationError(
                f"Answer must be a dictionary (got {answer})."
            )
        if not "answer" in answer:
            raise QuestionAnswerValidationError(
                f"Answer must have an 'answer' key (got {answer})."
            )

    def validate_answer_checkbox(self, answer: dict[str, Union[str, int]]) -> None:
        """Checks that answer["answer"] is a list of valid answer codes for a checkbox question"""
        answer_codes = answer["answer"]
        if not isinstance(answer_codes, list):
            raise QuestionAnswerValidationError(
                f"Answer must be a list of answer codes (got {answer_codes})."
            )
        try:
            answer_codes = [int(k) for k in answer["answer"]]
        except:
            raise QuestionAnswerValidationError(
                f"Answer codes must be a list of strings, bytes-like objects or real numbers (got {answer['answer']})."
            )
        acceptable_values = list(range(len(self.question_options)))
        for answer_code in answer_codes:
            if answer_code not in acceptable_values:
                raise QuestionAnswerValidationError(
                    f"Answer code {answer_code} has elements not in {acceptable_values}."
                )
        if self.min_selections is not None and len(answer_codes) < self.min_selections:
            raise QuestionAnswerValidationError(
                f"Answer {answer_codes} has fewer than {self.min_selections} options selected."
            )
        if self.max_selections is not None and len(answer_codes) > self.max_selections:
            raise QuestionAnswerValidationError(
                f"Answer {answer_codes} has more than {self.max_selections} options selected."
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
