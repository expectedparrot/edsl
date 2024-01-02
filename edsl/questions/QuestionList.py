import textwrap
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Type, Union
from edsl.questions import Question, QuestionData, AnswerData, Settings
from edsl.exceptions import QuestionAnswerValidationError
from edsl.utilities.utilities import random_string


class QuestionList(QuestionData):
    """Pydantic data model for QuestionList"""

    allow_nonresponse: Optional[bool] = False
    max_list_items: Optional[int] = None

    # see QuestionFreeText for an explanation of how __new__ works
    def __new__(cls, *args, **kwargs) -> "QuestionListEnhanced":
        instance = super(QuestionList, cls).__new__(cls)
        instance.__init__(*args, **kwargs)
        return QuestionListEnhanced(instance)

    def __init__(self, **data):
        super().__init__(**data)


class QuestionListEnhanced(Question):
    question_type = "list"

    def __init__(self, question: BaseModel):
        super().__init__(question)

    @property
    def instructions(self) -> str:
        return textwrap.dedent(
            """\
        {{question_text}}

        Your response should be only a valid JSON of the following format:
        {
            "answer": <list of comma-separated words or phrases >, 
            "comment": "<put comment here>"
        }
        {% if max_list_items is not none %}
        The list must not contain more than {{ max_list_items }} items.
        {% endif %}
        """
        )

    def translate_answer_code_to_answer(self, answer, scenario):
        """There is no answer code."""
        return answer

    def construct_answer_data_model(self) -> Type[BaseModel]:
        "Constructs the answer data model for this question"

        class QuestionListAnswerDataModel(AnswerData):
            answer: Union[list[str], list[dict]] = Field(
                ..., min_length=0, max_length=Settings.MAX_ANSWER_LENGTH
            )

            @field_validator("answer")
            def check_answer_nonresponse(cls, value):
                if (
                    hasattr(self, "allow_nonresponse")
                    and self.allow_nonresponse == False
                    and (value == [] or value is None)
                ):
                    raise QuestionAnswerValidationError("You must provide a response.")

                return value

            @field_validator("answer")
            def check_answer_length(cls, value):
                if (
                    hasattr(self, "max_list_items")
                    and self.max_list_items is not None
                    and (len(value) > self.max_list_items)
                ):
                    raise QuestionAnswerValidationError("Response has too many items.")
                return value

            @field_validator("answer")
            def check_answer_check(cls, value):
                if any([item == "" for item in value]):
                    raise QuestionAnswerValidationError(
                        f"Answer cannot contain empty strings, but got {value}."
                    )
                return value

        return QuestionListAnswerDataModel

    def simulate_answer(self):
        "Simulates a valid answer for debugging purposes (what the validator expects)"
        return {"answer": [random_string(), random_string()]}

    def form_elements(self):
        html_output = f"""
        <label for="{self.question_name}">{self.question_text}</label>
        <div id="{self.question_name}_div">
            <input type="text" id="{self.question_name}" name="{self.question_text}">
        </div>
        """
        return html_output


def main():  # pragma: no cover
    """This is a demo of how to use the QuestionList. It consumes API calls."""
    from edsl.language_models import LanguageModelOpenAIFour
    from edsl.questions import QuestionList

    m4 = LanguageModelOpenAIFour()

    question = QuestionList(
        question_text="What are some factors that could determine whether someone likes ice cream?",
        question_name="ice_cream_love_attributes",
        max_list_items=20,
    )

    results = question.by(m4).run()
    results.data[0].answer

    question = QuestionList(
        question_text="What are the most beloved sport teams in America?",
        question_name="most_beloved_teams",
        max_list_items=5,
    )

    results = question.by(m4).run()
    results.data[0].answer
