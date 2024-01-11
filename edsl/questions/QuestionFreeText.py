import textwrap
from edsl.utilities.utilities import random_string
from typing import Optional
from edsl.exceptions import QuestionAnswerValidationError
from edsl.questions import Question
from edsl.questions.descriptors import QuestionAllowNonresponseDescriptor


class QuestionFreeText(Question):
    default_instructions = textwrap.dedent(
        """\
        You are being asked the following question: {{question_text}}
        Return a valid JSON formatted like this: 
        {"answer": "<put free text answer here>"}
        """
    )

    question_type = "free_text"
    allow_nonresponse: bool = QuestionAllowNonresponseDescriptor()

    def __init__(
        self,
        question_text: str,
        question_name: str,
        allow_nonresponse: Optional[bool] = None,
        short_names_dict: Optional[dict[str, str]] = None,
        instructions: Optional[str] = None,
    ):
        self.question_text = question_text
        self.question_name = question_name
        self.instructions = instructions or self.default_instructions
        self.short_names_dict = short_names_dict or dict()

        self.allow_nonresponse = allow_nonresponse or False

    #############
    ## Validators
    #############

    def validate_answer(self, answer: dict[str, str]):
        """Validates the answer"""
        if "answer" not in answer:
            raise QuestionAnswerValidationError("Answer must have an 'answer' key!")
        return answer

    def translate_answer_code_to_answer(self, answer, scenario):
        """There is no answer code."""
        return answer

    def simulate_answer(self) -> dict[str, str]:
        return {"answer": random_string()}

    @classmethod
    def example(cls):
        return cls(
            question_text="How are you?",
            question_name="how_are_you",
            short_names_dict={"good": "good", "bad": "bad"},
            allow_nonresponse=True,
        )


if __name__ == "__main__":
    q = QuestionFreeText.example()
