import random
import textwrap
from typing import Any
from edsl.exceptions import QuestionAnswerValidationError
from edsl.questions import Question
from edsl.questions.descriptors import AnswerTemplateDescriptor
from edsl.utilities.utilities import random_string


class QuestionExtract(Question):
    question_type = "extract"

    default_instructions = textwrap.dedent(
        """\
        You are given the following input: "{{question_text}}".
        Create an ANSWER should be formatted like this {{ answer_template }},
        and it should have the same keys but values extracted from the input.
        If the value of an key is not present in the input, fill with "null".
        Return a valid JSON formatted like this: 
        {"answer": <put your ANSWER here>}
        ONLY RETURN THE JSON, AND NOTHING ELSE.
        """
    )

    answer_template: dict[str, Any] = AnswerTemplateDescriptor()

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

    def check_answer(self, value, acceptable_answer_keys):
        if any([key not in acceptable_answer_keys for key in value.keys()]):
            raise QuestionAnswerValidationError(
                f"Answer keys must be in {acceptable_answer_keys}, but got {value.keys()}"
            )
        if any([key not in value.keys() for key in acceptable_answer_keys]):
            raise QuestionAnswerValidationError(
                f"Answer must have all keys in {acceptable_answer_keys}, but got {value.keys()}"
            )

    def validate_answer(self, answer):
        value = answer["answer"]
        acceptable_answer_keys = set(self.answer_template.keys())
        self.check_answer(value, acceptable_answer_keys)
        return answer

    ################
    # Less important
    ################
    # TODO - ALL THE BELOW
    def translate_answer_code_to_answer(self, answer, scenario):
        return answer

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


# main
if __name__ == "__main__":
    from edsl.questions import QuestionExtract

    question = QuestionExtract(
        question_text="My name is Moby Dick. I have a PhD in astrology, but I'm actually a truck driver",
        answer_template={"name": "John Doe", "profession": "Carpenter"},
        question_name="extract_name",
    )
    question.run()

    question = QuestionExtract(
        question_text="Lorem Ipsum is simply dummy text of the printing and typesetting industry. Lorem Ipsum has been the industry's standard dummy text ever since the 1500s, when an unknown printer took a galley of type and scrambled it to make a type specimen book. It has survived not only five centuries, but also the leap into electronic typesetting, remaining essentially unchanged. It was popularised in the 1960s with the release of Letraset sheets containing Lorem Ipsum passages, and more recently with desktop publishing software like Aldus PageMaker including versions of Lorem Ipsum.",
        answer_template={"name": "John Doe", "profession": "Carpenter"},
        question_name="extract_name",
    )
    question.run()

    question = QuestionExtract(
        question_text="Please be advised that your timecard(s) are due to be submitted by 11:30 PM Sunday. Please log in to the time keeping portal to process your timecard. Thank you. Click Here to Login. Click Here to Login on your Mobile Device. Note: Please do not reply to this message, as it is system generated.",
        answer_template={"time_critical": "true", "system_generated": "false"},
        question_name="extract_email",
    )
    question.run()

    question = QuestionExtract(
        question_text="My name is Sam and I was born on 1992.",
        answer_template={"name": "John Doe", "age": 33},
        question_name="extract_name_age",
    )
    question.run()
