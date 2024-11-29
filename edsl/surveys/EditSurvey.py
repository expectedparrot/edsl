import copy
from typing import Union, Optional
from edsl.exceptions.surveys import SurveyError
from edsl.questions.QuestionBase import QuestionBase

from edsl.exceptions.surveys import SurveyError, SurveyCreationError
from .Rule import Rule
from .base import RulePriority, EndOfSurvey
from .RuleCollection import RuleCollection


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

    def delete_question(self, identifier: Union[str, int]) -> "Survey":
        """
        Delete a question from the survey.

        :param identifier: The name or index of the question to delete.
        :return: The updated Survey object.

        >>> from edsl import QuestionMultipleChoice, Survey
        >>> q1 = QuestionMultipleChoice(question_text="Q1", question_options=["A", "B"], question_name="q1")
        >>> q2 = QuestionMultipleChoice(question_text="Q2", question_options=["C", "D"], question_name="q2")
        >>> s = Survey().add_question(q1).add_question(q2)
        >>> _ = s.delete_question("q1")
        >>> len(s.questions)
        1
        >>> _ = s.delete_question(0)
        >>> len(s.questions)
        0
        """
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

        # Remove the question
        deleted_question = self.survey._questions.pop(index)
        del self.survey.pseudo_indices[deleted_question.question_name]

        # Update indices
        for question_name, old_index in self.survey.pseudo_indices.items():
            if old_index > index:
                self.survey.pseudo_indices[question_name] = old_index - 1

        # Update rules
        new_rule_collection = RuleCollection()
        for rule in self.survey.rule_collection:
            if rule.current_q == index:
                continue  # Remove rules associated with the deleted question
            if rule.current_q > index:
                rule.current_q -= 1
            if rule.next_q > index:
                rule.next_q -= 1

            if rule.next_q == index:
                if index == len(self.survey.questions):
                    rule.next_q = EndOfSurvey
                else:
                    rule.next_q = index

            new_rule_collection.add_rule(rule)
        self.survey.rule_collection = new_rule_collection

        # Update memory plan if it exists
        if hasattr(self.survey, "memory_plan"):
            self.survey.memory_plan.remove_question(deleted_question.question_name)

        return self.survey
