import random
from typing import Optional
from edsl.exceptions import QuestionCreationValidationError
from edsl.questions.QuestionCheckBox import QuestionCheckBox
from edsl.utilities import random_string


class QuestionTopK(QuestionCheckBox):
    """QuestionTopK is similar to QuestionCheckBox, but requires that the user selects exactly K among the question options."""

    question_type = "top_k"

    def __init__(
        self,
        question_name: str,
        question_text: str,
        question_options: list[str],
        min_selections: int,
        max_selections: int,
        short_names_dict: Optional[dict[str, str]] = None,
        instructions: Optional[str] = None,
    ):
        super().__init__(
            question_name=question_name,
            question_text=question_text,
            question_options=question_options,
            short_names_dict=short_names_dict,
            min_selections=min_selections,
            max_selections=max_selections,
            instructions=instructions,
        )
        if min_selections != max_selections:
            raise QuestionCreationValidationError(
                "TopK questions must have min_selections == max_selections"
            )
        if min_selections < 1:
            raise QuestionCreationValidationError(
                "TopK questions must have min_selections > 0"
            )

    def simulate_answer(self, human_readable=True) -> dict[str, str]:
        """Simulates a valid answer for debugging purposes"""
        if human_readable:
            # Select exactly self.min_selections options from self.question_options
            selected_options = random.sample(self.question_options, self.min_selections)
            answer = {
                "answer": selected_options,
                "comment": random_string(),
            }
        else:
            # Select exactly self.min_selections indexes from the range of self.question_options
            selected_indexes = random.sample(
                range(len(self.question_options)), self.min_selections
            )
            answer = {
                "answer": selected_indexes,
                "comment": random_string(),
            }
        return answer

    @classmethod
    def example(cls):
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
    q.instructions
    # validate an answer
    q.validate_answer({"answer": [0, 3], "comment": "I like custard"})
    # translate answer code
    q.translate_answer_code_to_answer([0, 3], {})
    # simulate answer
    q.simulate_answer()
    q.simulate_answer(human_readable=False)
    # serialization (inherits from Question)
    q.to_dict()
    q.from_dict(q.to_dict()) == q
