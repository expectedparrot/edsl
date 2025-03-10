from typing import Union, TYPE_CHECKING

if TYPE_CHECKING:
    from ...questions import QuestionBase
    from ..survey import Survey

from ..exceptions import SurveyError, SurveyCreationError
from .rule import Rule
from ..base import RulePriority, EndOfSurvey

class ValidatedString(str):
    def __new__(cls, content):
        if "<>" in content:
            raise SurveyCreationError(
                "The expression contains '<>', which is not allowed. You probably mean '!='."
            )
        return super().__new__(cls, content)


class RuleManager:
    def __init__(self, survey):
        self.survey = survey

    def _get_question_index(
        self, q: Union["QuestionBase", str, 'EndOfSurvey']
    ) -> Union[int, 'EndOfSurvey']:
        """Return the index of the question or EndOfSurvey object.

        :param q: The question or question name to get the index of.

        It can handle it if the user passes in the question name, the question object, or the EndOfSurvey object.

        >>> from edsl.questions import QuestionFreeText
        >>> from edsl import Survey
        >>> s = Survey.example()
        >>> s._get_question_index("q0")
        0

        This doesnt' work with questions that don't exist:

        >>> s._get_question_index("poop")
        Traceback (most recent call last):
        ...
        edsl.surveys.exceptions.SurveyError: Question name poop not found in survey. The current question names are {'q0': 0, 'q1': 1, 'q2': 2}.
        ...
        """
        if q == EndOfSurvey:
            return EndOfSurvey
        else:
            question_name = q if isinstance(q, str) else q.question_name
            if question_name not in self.survey.question_name_to_index:
                raise SurveyError(
                    f"""Question name {question_name} not found in survey. The current question names are {self.survey.question_name_to_index}."""
                )
            return self.survey.question_name_to_index[question_name]

    def _get_new_rule_priority(
        self, question_index: int, before_rule: bool = False
    ) -> int:
        """Return the priority for the new rule.

        :param question_index: The index of the question to add the rule to.
        :param before_rule: Whether the rule is evaluated before the question is answered.

        >>> from edsl import Survey
        >>> s = Survey.example()
        >>> RuleManager(s)._get_new_rule_priority(0)
        1
        """
        current_priorities = [
            rule.priority
            for rule in self.survey.rule_collection.applicable_rules(
                question_index, before_rule
            )
        ]
        if len(current_priorities) == 0:
            return RulePriority.DEFAULT.value + 1

        max_priority = max(current_priorities)
        # newer rules take priority over older rules
        new_priority = (
            RulePriority.DEFAULT.value
            if len(current_priorities) == 0
            else max_priority + 1
        )
        return new_priority

    def add_rule(
        self,
        question: Union["QuestionBase", str],
        expression: str,
        next_question: Union["QuestionBase", str, int],
        before_rule: bool = False,
    ) -> "Survey":
        """
        Add a rule to a Question of the Survey with the appropriate priority.

        :param question: The question to add the rule to.
        :param expression: The expression to evaluate.
        :param next_question: The next question to go to if the rule is true.
        :param before_rule: Whether the rule is evaluated before the question is answered.


        - The last rule added for the question will have the highest priority.
        - If there are no rules, the rule added gets priority -1.
        """
        question_index = self.survey._get_question_index(question)  # Fix

        # Might not have the name of the next question yet
        if isinstance(next_question, int):
            next_question_index = next_question
        else:
            next_question_index = self._get_question_index(next_question)

        new_priority = self._get_new_rule_priority(question_index, before_rule)  # fix

        self.survey.rule_collection.add_rule(
            Rule(
                current_q=question_index,
                expression=expression,
                next_q=next_question_index,
                question_name_to_index=self.survey.question_name_to_index,
                priority=new_priority,
                before_rule=before_rule,
            )
        )

        return self.survey

    def add_stop_rule(
        self, question: Union["QuestionBase", str], expression: str
    ) -> "Survey":
        """Add a rule that stops the survey.
        The rule is evaluated *after* the question is answered. If the rule is true, the survey ends.

        :param question: The question to add the stop rule to.
        :param expression: The expression to evaluate.

        If this rule is true, the survey ends.

        Here, answering "yes" to q0 ends the survey:

        >>> from edsl import Survey
        >>> s = Survey.example().add_stop_rule("q0", "{{ q0.answer }} == 'yes'")
        >>> s.next_question("q0", {"q0.answer": "yes"})
        EndOfSurvey

        By comparison, answering "no" to q0 does not end the survey:

        >>> s.next_question("q0", {"q0.answer": "no"}).question_name
        'q1'

        >>> s.add_stop_rule("q0", "{{ q1.answer }} <> 'yes'")
        Traceback (most recent call last):
        ...
        edsl.surveys.exceptions.SurveyCreationError: The expression contains '<>', which is not allowed. You probably mean '!='.
        ...
        """
        expression = ValidatedString(expression)
        prior_question_appears = False
        for prior_question in self.survey.questions:
            if prior_question.question_name in expression:
                prior_question_appears = True

        if not prior_question_appears:
            import warnings

            warnings.warn(
                f"The expression {expression} does not contain any prior question names. This is probably a mistake."
            )
        self.survey.add_rule(question, expression, EndOfSurvey)
        return self.survey


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)