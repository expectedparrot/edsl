from edsl.questions.descriptors import QuestionOptionsDescriptor
from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice


class QuestionYesNo(QuestionMultipleChoice):
    """Same as a QuestionMultipleChoice, but with question_options=["Yes","No"]"""

    question_type = "yes_no"
    question_options = QuestionOptionsDescriptor(num_choices=2)

    def __init__(
        self,
        question_name: str,
        question_text: str,
        short_names_dict: dict[str, str] = None,
        question_options: list[str] = ["Yes", "No"],
        instructions: str = None,
    ):
        super().__init__(
            question_name=question_name,
            question_text=question_text,
            question_options=question_options,
            short_names_dict=short_names_dict,
            instructions=instructions,
        )
        self.question_options = question_options

    ################
    # Example
    ################
    @classmethod
    def example(cls):
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
    q.instructions
    # validate an answer
    q.validate_answer({"answer": 0, "comment": "I like custard"})
    # translate answer code
    q.translate_answer_code_to_answer(0, {})
