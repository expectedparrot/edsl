from pydantic import BaseModel, Field
from typing import Type
from edsl.questions import Settings, QuestionData
from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoiceEnhanced


class QuestionLikertFive(QuestionData):
    """Pydantic data model for QuestionLikertFive"""

    question_text: str = Field(
        ..., min_length=1, max_length=Settings.MAX_QUESTION_LENGTH
    )
    question_options: list[str] = [
        "Strongly disagree",
        "Disagree",
        "Neutral",
        "Agree",
        "Strongly agree",
    ]

    def __new__(cls, *args, **kwargs):
        instance = super(QuestionLikertFive, cls).__new__(cls)
        instance.__init__(*args, **kwargs)
        return QuestionLikertFiveEnhanced(instance)


class QuestionLikertFiveEnhanced(QuestionMultipleChoiceEnhanced):
    """
    Inherits from QuestionMultipleChoice, because the two are similar.
    - A difference is that the answers in QuestionLikertFive are fixed
      and have a very specific order and labels
    """

    question_type = "likert_five"

    def __init__(self, question: BaseModel):
        super().__init__(question)

    def construct_answer_data_model(self) -> Type[BaseModel]:
        """Reuses the answer data model from QuestionMultipleChoiceEnhanced"""
        return super().construct_answer_data_model()

    # TODO: Seems that we need to have the label of each option?
    def form_elements(self):
        scale_values = ["1", "2", "3", "4", "5"]
        html_output = f"""
        <label>{self.question_text}</label>\n"""

        for index, value in enumerate(scale_values):
            html_output += f"""
            <div id="{self.question_name}_div_{index}">
                <input type="radio" id="{self.question_name}_{index}" 
                    name="{self.question_name}" value="{value}">
                <label for="{self.question_name}_{index}">{value}</label>
            </div>\n"""

        return html_output
