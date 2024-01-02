import random
import textwrap
from pydantic import BaseModel, model_validator
from typing import Any, Type
from edsl.questions import Question, QuestionData, AnswerData
from edsl.exceptions import QuestionAnswerValidationError
from edsl.utilities.utilities import random_string


class QuestionExtract(QuestionData):
    """Pydantic data model for QuestionExtract"""

    answer_template: dict[str, Any]

    # see QuestionFreeText for an explanation of how __new__ works
    def __new__(cls, *args, **kwargs) -> "QuestionExtractEnhanced":
        instance = super(QuestionExtract, cls).__new__(cls)
        instance.__init__(*args, **kwargs)
        return QuestionExtractEnhanced(instance)

    def __init__(self, **data):
        super().__init__(**data)


class QuestionExtractEnhanced(Question):
    question_type = "extract"

    def __init__(self, question: BaseModel):
        super().__init__(question)

    @property
    def instructions(self) -> str:
        return textwrap.dedent(
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

    def construct_answer_data_model(self) -> Type[BaseModel]:
        "Constructs the answer data model for this question"
        acceptable_answer_keys = set(self.answer_template.keys())

        class QuestionExtractAnswerDataModel(AnswerData):
            answer: dict

            @model_validator(mode="after")
            def check_answer(self):
                if any(
                    [key not in acceptable_answer_keys for key in self.answer.keys()]
                ):
                    raise QuestionAnswerValidationError(
                        f"Answer keys must be in {acceptable_answer_keys}, but got {self.answer.keys()}"
                    )
                if any(
                    [key not in self.answer.keys() for key in acceptable_answer_keys]
                ):
                    raise QuestionAnswerValidationError(
                        f"Answer must have all keys in {acceptable_answer_keys}, but got {self.answer.keys()}"
                    )

        return QuestionExtractAnswerDataModel

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

    def form_elements(self) -> str:
        html_output = f"\n\n\n<label>{self.question_text}</label>\n"
        return html_output


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
