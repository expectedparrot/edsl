from __future__ import annotations
import random
import textwrap
from typing import Any, Optional, Union
from edsl.questions.QuestionBase import QuestionBase
from edsl.questions.descriptors import IntegerDescriptor, QuestionOptionsDescriptor
from edsl.scenarios import Scenario
from edsl.utilities import random_string


class QuestionBudget(QuestionBase):
    """This question prompts the agent to allocate a budget among options."""

    question_type = "budget"
    budget_sum: int = IntegerDescriptor(none_allowed=False)
    question_options: list[str] = QuestionOptionsDescriptor()

    def __init__(
        self,
        question_name: str,
        question_text: str,
        question_options: list[str],
        budget_sum: int,
    ):
        """Instantiate a new QuestionBudget.

        :param question_name: The name of the question.
        :param question_text: The text of the question.
        :param question_options: The options for allocation of the budget sum.
        :param budget_sum: The total amount of the budget to be allocated among the options.
        :param instructions: Instructions for the question. If not provided, the default instructions are used. To view them, run `QuestionBudget.default_instructions`.
        """
        self.question_name = question_name
        self.question_text = question_text
        self.question_options = question_options
        self.budget_sum = budget_sum

    ################
    # Answer methods
    ################
    def _validate_answer(self, answer: dict[str, Any]) -> dict[str, Union[int, str]]:
        """Validate the answer."""
        self._validate_answer_template_basic(answer)
        self._validate_answer_key_value(answer, "answer", dict)
        self._validate_answer_budget(answer)
        return answer

    def _translate_answer_code_to_answer(
        self, answer_codes: dict[str, int], scenario: Scenario = None
    ):
        """
        Translate the answer codes to the actual answers.

        For example, for a budget question with options ["a", "b", "c"],
        the answer codes are 0, 1, and 2. The LLM will respond with 0.
        This code will translate that to "a".
        """
        translated_codes = []
        for answer_code, response in answer_codes.items():
            translated_codes.append({self.question_options[int(answer_code)]: response})

        return translated_codes

    def _simulate_answer(self, human_readable=True):
        """Simulate a valid answer for debugging purposes (what the validator expects)."""
        if human_readable:
            keys = self.question_options
        else:
            keys = range(len(self.question_options))
        remaining_budget = self.budget_sum
        values = []
        for _ in range(len(self.question_options)):
            if _ == len(self.question_options) - 1:
                # Assign remaining budget to the last value
                values.append(remaining_budget)
            else:
                # Generate a random value between 0 and remaining budget
                value = random.randint(0, remaining_budget)
                values.append(value)
                remaining_budget -= value
        answer = dict(zip(keys, values))
        return {
            "answer": answer,
            "comment": random_string(),
        }

    ################
    # Helpful methods
    ################
    @classmethod
    def example(cls) -> QuestionBudget:
        """Return an example of a budget question."""
        return cls(
            question_name="food_budget",
            question_text="How would you allocate $100?",
            question_options=["Pizza", "Ice Cream", "Burgers", "Salad"],
            budget_sum=100,
        )


def main():
    """Create an example of a budget question and demonstrate its functionality."""
    from edsl.questions.QuestionBudget import QuestionBudget

    q = QuestionBudget.example()
    q.question_text
    q.question_options
    q.question_name
    # validate an answer
    q._validate_answer(
        {"answer": {0: 100, 1: 0, 2: 0, 3: 0}, "comment": "I like custard"}
    )
    # translate answer code
    q._translate_answer_code_to_answer({0: 100, 1: 0, 2: 0, 3: 0})
    # simulate answer
    q._simulate_answer()
    q._simulate_answer(human_readable=False)
    q._validate_answer(q._simulate_answer(human_readable=False))
    # serialization (inherits from Question)
    q.to_dict()
    assert q.from_dict(q.to_dict()) == q


if __name__ == "__main__":
    q = QuestionBudget.example()
    results = q.run()

    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
