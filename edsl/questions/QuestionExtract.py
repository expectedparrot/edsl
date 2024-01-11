from __future__ import annotations
import random
import textwrap
from typing import Any, Optional
from edsl.questions import Question
from edsl.questions.descriptors import AnswerTemplateDescriptor
from edsl.scenarios import Scenario
from edsl.utilities import random_string


class QuestionExtract(Question):
    """
    This question asks the user to extract values from a string, and return them in a given template.

    Arguments:
    - `question_name` is the name of the question (string)
    - `question_text` is the text of the question (string)
    - `answer_template` is the template for the answer (dictionary mapping strings to strings)

    Optional arguments:
    - `instructions` are the instructions for the question (string). If not provided, the default instructions are used. To view them, run `QuestionExtract.default_instructions`

    For an example, run `QuestionExtract.example()`
    """

    question_type = "extract"
    answer_template: dict[str, Any] = AnswerTemplateDescriptor()
    default_instructions = textwrap.dedent(
        """\
        You are given the following input: "{{question_text}}".
        Create an ANSWER should be formatted like this: "{{ answer_template }}",
        and it should have the same keys but values extracted from the input.
        If the value of a key is not present in the input, fill with "null".
        Return a valid JSON formatted like this: 
        {"answer": <put your ANSWER here>}
        ONLY RETURN THE JSON, AND NOTHING ELSE.
        """
    )

    def __init__(
        self,
        question_text: str,
        answer_template: dict[str, Any],
        question_name: str,
        instructions: Optional[str] = None,
    ):
        self.question_name = question_name
        self.question_text = question_text
        self.answer_template = answer_template
        self.instructions = instructions or self.default_instructions

    ################
    # Answer methods
    ################
    def validate_answer(self, answer: Any) -> dict[str, Any]:
        self.validate_answer_template_basic(answer)
        self.validate_answer_extract(answer)
        return answer

    def translate_answer_code_to_answer(self, answer, scenario: Scenario = None):
        """Returns the answer in a human-readable format"""
        return answer

    # TODO - ALL THE BELOW
    def simulate_answer(self, human_readable=True) -> dict[str, str]:
        """Simulates a valid answer for debugging purposes"""
        if human_readable:
            answer = random.choice(self.question_options)
        else:
            answer = random.choice(range(len(self.question_options)))
        return {
            "answer": answer,
            "comment": random_string(),
        }

    ################
    # Helpful methods
    ################
    @classmethod
    def example(cls) -> QuestionExtract:
        return cls(
            question_name="extract_name",
            question_text="My name is Moby Dick. I have a PhD in astrology, but I'm actually a truck driver",
            answer_template={"name": "John Doe", "profession": "Carpenter"},
        )


# main
def main():
    from edsl.questions.QuestionExtract import QuestionExtract

    q = QuestionExtract.example()
