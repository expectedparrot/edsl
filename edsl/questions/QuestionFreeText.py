import textwrap
from edsl.utilities.utilities import random_string
from typing import Optional
from edsl.questions import Question
from edsl.questions.ValidatorMixin import ValidatorMixin
from edsl.exceptions import QuestionAnswerValidationError


class QuestionFreeText(Question, ValidatorMixin):
    default_instructions = textwrap.dedent(
        """\
        You are being asked the following question: {{question_text}}
        Return a valid JSON formatted like this: 
        {"answer": "<put free text answer here>"}
        """
    )

    question_type = "free_text"

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

        # custom instructions
        if set_instructions := (instructions is not None):
            self.instructions = self.instructions
        else:
            self.instructions = self.default_instructions
        self.set_instructions = set_instructions

        # non-response
        if set_allow_nonresponse := (allow_nonresponse is not None):
            self.allow_nonresponse = allow_nonresponse
        else:
            self.allow_nonresponse = False

        # Short-names dictionary
        if set_short_names_dict := (short_names_dict is not None):
            self.short_names_dict = dict()
        else:
            self.short_names_dict = short_names_dict

    #############
    ## Validators
    #############

    @property
    def allow_nonresponse(self):
        return self._allow_nonresponse

    @allow_nonresponse.setter
    def allow_nonresponse(self, value):
        self._allow_nonresponse = self.validate_allow_nonresponse(value)

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
