from __future__ import annotations
from typing import Any
from edsl.questions.QuestionBase import QuestionBase
from edsl.questions.descriptors import AnswerTemplateDescriptor
from edsl.scenarios import Scenario
from edsl.utilities import random_string


class QuestionExtract(QuestionBase):
    """This question prompts the agent to extract information from a string and return it in a given template."""

    question_type = "extract"
    answer_template: dict[str, Any] = AnswerTemplateDescriptor()

    def __init__(
        self,
        question_text: str,
        answer_template: dict[str, Any],
        question_name: str,
    ):
        """Initialize the question.

        :param question_name: The name of the question.
        :param question_text: The text of the question.
        :param question_options: The options the respondent should select from.
        :param answer_template: The template for the answer.
        :param instructions: Instructions for the question. If not provided, the default instructions are used. To view them, run `QuestionExtract.default_instructions`.
        """
        self.question_name = question_name
        self.question_text = question_text
        self.answer_template = answer_template

    ################
    # Answer methods
    ################
    def _validate_answer(self, answer: Any) -> dict[str, Any]:
        """Validate the answer."""
        # raw_json = answer["answer"]
        # fixed_json_data = re.sub(r"\'", '"', raw_json)
        # answer["answer"] = json.loads(fixed_json_data)
        self._validate_answer_template_basic(answer)
        # self._validate_answer_key_value(answer, "answer", dict)

        self._validate_answer_extract(answer)
        return answer

    def _translate_answer_code_to_answer(self, answer, scenario: Scenario = None):
        """Return the answer in a human-readable format."""
        return answer

    def _simulate_answer(self, human_readable: bool = True) -> dict[str, str]:
        """Simulate a valid answer for debugging purposes."""
        return {
            "answer": {key: random_string() for key in self.answer_template.keys()},
            "comment": random_string(),
        }

    ################
    # Helpful methods
    ################
    @classmethod
    def example(cls) -> QuestionExtract:
        """Return an example question."""
        return cls(
            question_name="extract_name",
            question_text="My name is Moby Dick. I have a PhD in astrology, but I'm actually a truck driver",
            answer_template={"name": "John Doe", "profession": "Carpenter"},
        )


def main():
    """Administer a question and validate the answer."""
    from edsl.questions.QuestionExtract import QuestionExtract

    q = QuestionExtract.example()
    q.question_text
    q.question_name
    q.answer_template
    q._validate_answer({"answer": {"name": "Moby", "profession": "truck driver"}})
    q._translate_answer_code_to_answer(
        {"answer": {"name": "Moby", "profession": "truck driver"}}
    )
    q._simulate_answer()
    q._simulate_answer(human_readable=False)
    q._validate_answer(q._simulate_answer(human_readable=False))
    # serialization (inherits from Question)
    q.to_dict()
    assert q.from_dict(q.to_dict()) == q

    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
