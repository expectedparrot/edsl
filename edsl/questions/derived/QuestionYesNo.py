from __future__ import annotations
from edsl.questions.descriptors import QuestionOptionsDescriptor
from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice


class QuestionYesNo(QuestionMultipleChoice):
    """
    This question asks the user to respond with "Yes" or "No".

    Arguments:
    - `question_name` is the name of the question (string)
    - `question_text` is the text of the question (string)
    - `question_options` are the options the user should select from (list of strings)

    Optional arguments:
    - `instructions` are the instructions for the question (string). If not provided, the default instructions are used. To view them, run `QuestionYesNo.default_instructions`
    - `short_names_dict` maps question_options to short names (dictionary mapping strings to strings)

    For an example, see `QuestionYesNo.example()`
    """

    question_type = "yes_no"
    question_options = QuestionOptionsDescriptor(num_choices=2)

    def __init__(
        self,
        question_name: str,
        question_text: str,
        short_names_dict: dict[str, str] = None,
        question_options: list[str] = ["Yes", "No"],
    ):
        super().__init__(
            question_name=question_name,
            question_text=question_text,
            question_options=question_options,
            short_names_dict=short_names_dict,
        )
        self.question_options = question_options

    ################
    # Helpful
    ################
    @classmethod
    def example(cls) -> QuestionYesNo:
        return cls(
            question_name="is_it_raining",
            question_text="Is it raining?",
            short_names_dict={"Yes": "y", "No": "y"},
        )


def main():
    from edsl.questions.derived.QuestionYesNo import QuestionYesNo

    q = QuestionYesNo.example()
    q.question_text
    q.question_options
    q.question_name
    q.short_names_dict
    # validate an answer
    q.validate_answer({"answer": 0, "comment": "I like custard"})
    # translate answer code
    q.translate_answer_code_to_answer(0, {})
    q.simulate_answer()
    q.simulate_answer(human_readable=False)
    q.validate_answer(q.simulate_answer(human_readable=False))
    # serialization (inherits from Question)
    q.to_dict()
    assert q.from_dict(q.to_dict()) == q
