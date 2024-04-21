from __future__ import annotations
from edsl.questions.descriptors import QuestionOptionsDescriptor
from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice


class QuestionYesNo(QuestionMultipleChoice):
    """This question prompts the agent to respond with 'Yes' or 'No'."""

    question_type = "yes_no"
    question_options = QuestionOptionsDescriptor(num_choices=2)

    def __init__(
        self,
        question_name: str,
        question_text: str,
        question_options: list[str] = ["Yes", "No"],
    ):
        """Instantiate a new QuestionYesNo.

        :param question_name: The name of the question.
        :param question_text: The text of the question.
        :param instructions: Instructions for the question. If not provided, the default instructions are used. To view them, run `QuestionYesNo.default_instructions`.
        """
        super().__init__(
            question_name=question_name,
            question_text=question_text,
            question_options=question_options,
        )
        self.question_options = question_options

    ################
    # Helpful
    ################
    @classmethod
    def example(cls) -> QuestionYesNo:
        """Return an example of a yes/no question."""
        return cls(question_name="is_it_raining", question_text="Is it raining?")


def main():
    """Create an example of a yes/no question and demonstrate its functionality."""
    from edsl.questions.derived.QuestionYesNo import QuestionYesNo

    q = QuestionYesNo.example()
    q.question_text
    q.question_options
    q.question_name
    # validate an answer
    q._validate_answer({"answer": 0, "comment": "I like custard"})
    # translate answer code
    q._translate_answer_code_to_answer(0, {})
    q._simulate_answer()
    q._simulate_answer(human_readable=False)
    q._validate_answer(q._simulate_answer(human_readable=False))
    # serialization (inherits from Question)
    q.to_dict()
    assert q.from_dict(q.to_dict()) == q

    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
