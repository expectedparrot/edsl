from __future__ import annotations
import re
import json
from typing import Any
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

    def __init__(
        self,
        question_text: str,
        answer_template: dict[str, Any],
        question_name: str,
    ):
        self.question_name = question_name
        self.question_text = question_text
        self.answer_template = answer_template

    ################
    # Answer methods
    ################
    def validate_answer(self, answer: Any) -> dict[str, Any]:
        """Validates the answer"""
        # raw_json = answer["answer"]
        # fixed_json_data = re.sub(r"\'", '"', raw_json)
        # answer["answer"] = json.loads(fixed_json_data)
        self.validate_answer_template_basic(answer)
        # self.validate_answer_key_value(answer, "answer", dict)

        self.validate_answer_extract(answer)
        return answer

    def translate_answer_code_to_answer(self, answer, scenario: Scenario = None):
        """Returns the answer in a human-readable format"""
        return answer

    def simulate_answer(self, human_readable: bool = True) -> dict[str, str]:
        """Simulates a valid answer for debugging purposes"""
        return {
            "answer": {key: random_string() for key in self.answer_template.keys()},
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
    q.question_text
    q.question_name
    q.answer_template
    q.validate_answer({"answer": {"name": "Moby", "profession": "truck driver"}})
    q.translate_answer_code_to_answer(
        {"answer": {"name": "Moby", "profession": "truck driver"}}
    )
    # simulate answer
    q.simulate_answer()
    q.simulate_answer(human_readable=False)
    q.validate_answer(q.simulate_answer(human_readable=False))
    # serialization (inherits from Question)
    q.to_dict()
    assert q.from_dict(q.to_dict()) == q
