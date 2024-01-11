from typing import Any, Type, Union
from edsl.exceptions import (
    QuestionAnswerValidationError,
)


class AnswerValidatorMixin:
    """AnswerValidatorMixin"""

    #####################
    # TEMPLATE VALIDATION
    #####################
    def validate_answer_template_basic(self, answer: Any) -> None:
        """Checks that the answer (i) is a dictionary (ii) has an 'answer' key"""
        if not isinstance(answer, dict):
            raise QuestionAnswerValidationError(
                f"Answer must be a dictionary (got {answer})."
            )
        if not "answer" in answer:
            raise QuestionAnswerValidationError(
                f"Answer must have an 'answer' key (got {answer})."
            )

    #####################
    # VALUE VALIDATION
    #####################
    def validate_answer_key_value(
        self, answer: dict[str, Any], key: str, of_type: Type
    ) -> None:
        """Checks that the value of a key is of the specified type"""
        if not isinstance(answer.get(key), of_type):
            raise QuestionAnswerValidationError(
                f"Answer key '{key}' must be of type {of_type.__name__} (got {answer.get(key)})."
            )

    #####################
    # QUESTION SPECIFIC VALIDATION
    #####################
    def validate_answer_budget(self, answer: dict[str, Any]) -> None:
        """Checks that the 'answer' key value adheres to QuestioBudget-specific rules"""
        answer = answer.get("answer")
        budget_sum = self.budget_sum
        acceptable_answer_keys = set(range(len(self.question_options)))
        answer_keys = set([int(k) for k in answer.keys()])
        current_sum = sum(answer.values())
        if not current_sum == budget_sum:
            raise QuestionAnswerValidationError(
                f"Budget sum must be {budget_sum}, but got {current_sum}."
            )
        if any(v < 0 for v in answer.values()):
            raise QuestionAnswerValidationError(
                f"Budget values must be positive, but got {answer_keys}."
            )
        if any([int(key) not in acceptable_answer_keys for key in answer.keys()]):
            raise QuestionAnswerValidationError(
                f"Budget keys must be in {acceptable_answer_keys}, but got {answer_keys}"
            )
        if acceptable_answer_keys != answer_keys:
            missing_keys = acceptable_answer_keys - answer_keys
            raise QuestionAnswerValidationError(
                f"All but keys must be represented in the answer. Missing: {missing_keys}"
            )

    def validate_answer_checkbox(self, answer: dict[str, Union[str, int]]) -> None:
        """Checks that the value of the 'answer' key is a list of valid answer codes for a checkbox question"""
        answer_codes = answer["answer"]
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
