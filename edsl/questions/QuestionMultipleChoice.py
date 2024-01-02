import random
import textwrap
from jinja2 import Template
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Type
from edsl.questions import Question, QuestionData, AnswerData, Settings
from edsl.exceptions import QuestionAnswerValidationError
from edsl.utilities.utilities import random_string


class QuestionMultipleChoice(QuestionData):
    """Pydantic data model for QuestionMultipleChoice"""

    question_options: list[str] = Field(
        ...,
        min_length=Settings.MIN_NUM_OPTIONS,
        max_length=Settings.MAX_NUM_OPTIONS,
    )

    # see QuestionFreeText for an explanation of how __new__ works
    def __new__(cls, *args, **kwargs) -> "QuestionMultipleChoiceEnhanced":
        instance = super(QuestionMultipleChoice, cls).__new__(cls)
        instance.__init__(*args, **kwargs)
        return QuestionMultipleChoiceEnhanced(instance)

    def __init__(self, **data):
        super().__init__(**data)

    @field_validator("question_options")
    def check_unique(cls, value):
        return cls.base_validator_check_unique(value)

    @field_validator("question_options")
    def check_option_string_lengths(cls, value):
        return cls.base_validator_check_option_string_lengths(value)


class QuestionMultipleChoiceEnhanced(Question):
    question_type = "multiple_choice"

    def __init__(self, question: BaseModel):
        super().__init__(question)

    @property
    def instructions(self) -> str:
        return textwrap.dedent(
            """\
        You are being asked the following question: {{question_text}}
        The options are 
        {% for option in question_options %}
        {{ loop.index0 }}: {{option}}
        {% endfor %}                       
        Return a valid JSON formatted like this, selecting only the number of the option: 
        {"answer": <put answer code here>, "comment": "<put explanation here>"}
        Only 1 option may be selected.
        """
        )

    def construct_answer_data_model(self) -> Type[BaseModel]:
        "Constructs the answer data model for this question"
        acceptable_values = range(len(self.question_options))

        class QuestionMultipleChoiceAnswerDataModel(AnswerData):
            answer: int
            comment: Optional[str] = None

            @field_validator("answer")
            def check_answer(cls, value):
                if value in acceptable_values:
                    return value
                else:
                    raise QuestionAnswerValidationError(
                        f"Answer {value} not in acceptable values {acceptable_values}"
                    )

        return QuestionMultipleChoiceAnswerDataModel

    ################
    # Less important
    ################

    def translate_answer_code_to_answer(self, answer_code, scenario=None):
        """
        Translates the answer code to the actual answer.
        For example, for question_options ["a", "b", "c"], the answer codes are 0, 1, and 2.
        The LLM will respond with 0, and this code will translate that to "a".
        # TODO: REMOVE
        >>> q = QuestionMultipleChoice(question_text = "How are you?", question_options = ["Good", "Great", "OK", "Bad"], question_name = "how_feeling")
        >>> q.translate_answer_code_to_answer(0, {})
        'Good'
        """
        scenario = scenario or dict()
        translated_options = [
            Template(str(option)).render(scenario) for option in self.question_options
        ]
        return translated_options[int(answer_code)]

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
        for index, option in enumerate(self.question_options):
            html_output += f"""
            <div id = "{self.question_name}_div_{index}">
                <input type="radio" id="{self.question_name}_{index}" name="{self.question_text}" value="{option}">
                <label for="{self.question_name}_{index}">{option}</label>
            </div>\n
            """
        return html_output


if __name__ == "__main__":
    from edsl.questions import QuestionMultipleChoice

    q = QuestionMultipleChoice(
        question_text="Do you enjoying eating custard while skydiving?",
        question_options=["yes, somtimes", "no", "only on Tuesdays"],
        question_name="goose_fight",
    )
    results = q.run()
    print(results)
