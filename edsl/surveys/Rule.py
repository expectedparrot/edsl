"""The Rule class defines a rule for determining the next question presented to an agent.

The key component is an expression specifiying the logic of the rule, which can include any combination of logical operators ('and', 'or', 'not'), e.g.:

.. code-block:: python

    "q1 == 'yes' or q2 == 'no'"

The expression must be about questions "before" the current question.

Only one rule should apply at each priority level.
If multiple rules apply, the one with the highest priority is used. 
If there are conflicting rules, an exception is raised.

If no rule is specified, the next question is given as the default.
When a question is added with index, it is always given a rule the next question is index + 1, but
with a low (-1) priority.
"""
import ast
from collections import namedtuple
from rich import print
from simpleeval import EvalWithCompoundTypes
from typing import Any, Union, List
from edsl.exceptions import (
    SurveyRuleCannotEvaluateError,
    SurveyRuleCollectionHasNoRulesAtNodeError,
    SurveyRuleRefersToFutureStateError,
    SurveyRuleReferenceInRuleToUnknownQuestionError,
    SurveyRuleSendsYouBackwardsError,
    SurveyRuleSkipLogicSyntaxError,
)
from edsl.surveys.base import EndOfSurvey
from edsl.utilities.ast_utilities import extract_variable_names
from edsl.utilities.interface import print_table_with_rich


class Rule:
    """The Rule class defines a "rule" for determining the next question presented to an agent."""

    # Not implemented but nice to have:
    # We could potentially use the question pydantic models to check for rule conflicts, as
    # they define the potential trees through a survey.

    # We could also use the AST to check for conflicts by inspecting the types of a rule.
    # For example, if we know the answer to a question is a string, we could check that
    # the expression only contains string comparisons.

    def __init__(
        self,
        current_q: int,
        expression: str,
        next_q: Union[int, EndOfSurvey.__class__],
        question_name_to_index: dict[str, int],
        priority: int,
    ):
        """Represent a rule for determining the next question presented to an agent.

        Questions are represented by int indices.

        :param current_q: The question at which the rule is potentially applied.
        :param expression: A string that evaluates to true or false. If true, then next_q is next.
        :param next_q: The next question if the expression is true.
        :param question_name_to_index: A dictionary mapping question names to indices.
        :param priority: An integer that determines which rule is applied, if multiple rules apply.
        """
        self.current_q = current_q
        self.expression = expression
        self.next_q = next_q
        self.question_name_to_index = question_name_to_index
        self.priority = priority

        if not next_q == EndOfSurvey and current_q > next_q:
            raise SurveyRuleSendsYouBackwardsError

        # get the AST for the expression - used to extract
        # the variables referenced in the expression
        try:
            self.ast_tree = ast.parse(self.expression)
        except SyntaxError:
            raise SurveyRuleSkipLogicSyntaxError

        # get the names of the variables in the expression
        # e.g., q1 == 'yes' -> ['q1']
        extracted_question_names = extract_variable_names(self.ast_tree)

        # make sure all the variables in the expression are known questions
        try:
            assert all([q in question_name_to_index for q in extracted_question_names])
        except AssertionError:
            print(f"Question name to index: {question_name_to_index}")
            print(f"Extracted question names: {extracted_question_names}")
            raise SurveyRuleReferenceInRuleToUnknownQuestionError

        # get the indices of the questions mentioned in the expression
        self.named_questions_by_index = [
            question_name_to_index[q] for q in extracted_question_names
        ]

        # A rule should only refer to questions that have already been asked.
        # so the named questions in the expression should not be higher than the current question
        if self.named_questions_by_index:
            if max(self.named_questions_by_index) > self.current_q:
                raise SurveyRuleRefersToFutureStateError

    def to_dict(self):
        """Convert the rule to a dictionary for serialization."""
        return {
            "current_q": self.current_q,
            "expression": self.expression,
            "next_q": "EndOfSurvey" if self.next_q == EndOfSurvey else self.next_q,
            "priority": self.priority,
            "question_name_to_index": self.question_name_to_index,
        }

    @classmethod
    def from_dict(self, rule_dict):
        """Create a rule from a dictionary."""
        if rule_dict["next_q"] == "EndOfSurvey":
            rule_dict["next_q"] = EndOfSurvey

        return Rule(
            current_q=rule_dict["current_q"],
            expression=rule_dict["expression"],
            next_q=rule_dict["next_q"],
            priority=rule_dict["priority"],
            question_name_to_index=rule_dict["question_name_to_index"],
        )

    def __repr__(self):
        """Pretty-print the rule."""
        return f'Rule(current_q={self.current_q}, expression="{self.expression}", next_q={self.next_q}, priority={self.priority}, question_name_to_index={self.question_name_to_index})'

    def __str__(self):
        """Return a string representation of the rule."""
        return self.__repr__()

    @property
    def question_index_to_name(self):
        """Reverse the dictionary do we can look up questions by name."""
        return {v: k for k, v in self.question_name_to_index.items()}

    def show_ast_tree(self):
        """Pretty-print the AST tree to the terminal."""
        print(
            ast.dump(
                self.ast_tree, annotate_fields=True, indent=4, include_attributes=True
            )
        )

    def evaluate(self, answers: dict[int, Any]):
        """Compute the value of the expression, given a dictionary of known questions answers.

        If the expression cannot be evaluated, it raises a CannotEvaluate exception.
        """

        def substitute_in_answers(expression, answers):
            """Take the dictionary of answers and substitute them into the expression."""
            for var, value in answers.items():
                # If it is a string, add quotes; otherwise, just convert to string.
                if isinstance(value, str):
                    replacement = f"'{value}'"
                else:
                    replacement = str(value)

                expression = expression.replace(var, replacement)
            return expression

        try:
            to_evaluate = substitute_in_answers(self.expression, answers)
            return EvalWithCompoundTypes().eval(to_evaluate)
        except Exception as e:
            print(f"Exception in evaluation: {e}")
            raise SurveyRuleCannotEvaluateError


if __name__ == "__main__":
    r = Rule(
        current_q=1,
        expression="q1 == 'yes'",
        next_q=2,
        question_name_to_index={"q1": 1},
        priority=0,
    )
