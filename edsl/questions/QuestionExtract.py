from __future__ import annotations
import random
import textwrap
from typing import Any
from edsl.questions import Question
from edsl.questions.descriptors import AnswerTemplateDescriptor
from edsl.scenarios import Scenario
from edsl.utilities import random_string


class QuestionExtract(Question):
    question_type = "extract"
    answer_template: dict[str, Any] = AnswerTemplateDescriptor()
    default_instructions = textwrap.dedent(
        """\
        You are given the following input: "{{question_text}}".
        Create an ANSWER should be formatted like this {{ answer_template }},
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
        short_names_dict: dict[str, str] = None,
        instructions: str = None,
    ):
        self.question_text = question_text
        self.answer_template = answer_template
        self.question_name = question_name
        self.instructions = instructions or self.default_instructions
        self.short_names_dict = short_names_dict or dict()

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
