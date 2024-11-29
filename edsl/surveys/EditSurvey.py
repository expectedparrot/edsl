from typing import Union
from edsl.exceptions.surveys import SurveyError


class EditSurvey:

    def __init__(self, survey):
        self.survey = survey

    def move_question(self, identifier: Union[str, int], new_index: int) -> "Survey":
        if isinstance(identifier, str):
            if identifier not in self.survey.question_names:
                raise SurveyError(
                    f"Question name '{identifier}' does not exist in the survey."
                )
            index = self.survey.question_name_to_index[identifier]
        elif isinstance(identifier, int):
            if identifier < 0 or identifier >= len(self.survey.questions):
                raise SurveyError(f"Index {identifier} is out of range.")
            index = identifier
        else:
            raise SurveyError(
                "Identifier must be either a string (question name) or an integer (question index)."
            )

        moving_question = self.survey._questions[index]

        new_survey = self.survey.delete_question(index)
        new_survey.add_question(moving_question, new_index)
        return new_survey
