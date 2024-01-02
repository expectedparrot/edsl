import ast
from collections import namedtuple
from rich import print
from simpleeval import EvalWithCompoundTypes
from typing import Any, Union
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
    """
    The class defines a a "rule" for what question an agent should be presented next.

    The key structure of a rule is:
    - current_q: The question at which the rule is potentially applied (an index)
    - expression: A string that if evaluates to true, then next_q (an index) is next
    - next_q: The question is true
    - priority: an integer that determines which rule is applied if multiple rules apply

    The key part of this is expression specifiying the skip logic.
    An expression can be any combination of and/or/not/parenthesis etc.

            "q1 == 'yes' or q2 == 'no'"

    The skip-logic expression has to be about questions "before" the current node.
    To determine the value of the expression, we currently, we use eval.
    Eventually, we'll use the AST of the expression to make it safer.

    If multiple rules apply, the one with the highest priority is used.
    This is to deal with the fact that when we create a survey, we give the
    next question as the default.
    So when a question is added with index, it is always given a rule the next question is index + 1, but
    given a low (-1) priority.

    Only one rule should apply at each priority level.
    If there are conflicting rules, an exception is raised.
    Ideally, we'd have a way to resolve this ex ante, perhaps to traversing the implied tree
    each time a rule is added, but for now, we'll let the error emerge at run-time.

    ## Not implemented but nice to have
    We could potentially use the question pydantic models to check for rule conflicts, as
    they define the potential trees through a survey.

    We could also use the AST to check for conflicts by inspecting the types of a rule.
    For example, if we know the answer to a question is a string, we could check that
    the expression only contains string comparisons.
    This would be a lot of work.
    """

    def __init__(
        self,
        current_q: int,
        expression: str,
        next_q: Union[int, EndOfSurvey],
        question_name_to_index: dict[str, int],
        priority: int,
    ):
        """Questions are represented by int indices."""

        self.current_q = current_q
        self.expression = expression
        self.next_q = next_q
        self.priority = priority
        self.question_name_to_index = question_name_to_index

        if not isinstance(next_q, EndOfSurvey) and current_q > next_q:
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
        return {
            "current_q": self.current_q,
            "expression": self.expression,
            "next_q": "EndOfSurvey"
            if isinstance(self.next_q, EndOfSurvey)
            else self.next_q,
            "priority": self.priority,
            "question_name_to_index": self.question_name_to_index,
        }

    @classmethod
    def from_dict(self, rule_dict):
        if rule_dict["next_q"] == "EndOfSurvey":
            rule_dict["next_q"] = EndOfSurvey()

        return Rule(
            current_q=rule_dict["current_q"],
            expression=rule_dict["expression"],
            next_q=rule_dict["next_q"],
            priority=rule_dict["priority"],
            question_name_to_index=rule_dict["question_name_to_index"],
        )

    def __repr__(self):
        return f'Rule(current_q = {self.current_q}, expression = "{self.expression}", next_q = {self.next_q}, priority = {self.priority})'

    def __str__(self):
        return self.__repr__()

    @property
    def question_index_to_name(self):
        """Reverses the dictionary do we can look up questions by name"""
        return {v: k for k, v in self.question_name_to_index.items()}

    def show_ast_tree(self):
        """Pretty-prints the AST tree to the terminal"""
        print(
            ast.dump(
                self.ast_tree, annotate_fields=True, indent=4, include_attributes=True
            )
        )

    def evaluate(self, answers: dict[int, Any]):
        """
        Computes the value of the expression, given a dictionary of known questions answers.
        If the expression cannot be evaluated, it raises a CannotEvaluate exception.
        """

        def substitute_in_answers(expression, answers):
            "Take the dictionary of answers and substitute them into the expression"
            for var, value in answers.items():
                # If it's a string, add quotes; otherwise, just convert to string
                if isinstance(value, str):
                    replacement = f"'{value}'"
                else:
                    replacement = str(value)

                expression = expression.replace(var, replacement)
            return expression

        try:
            return EvalWithCompoundTypes().eval(
                substitute_in_answers(self.expression, answers)
            )
        except Exception as e:
            print(f"Exception in evaluation: {e}")
            raise SurveyRuleCannotEvaluateError


NextQuestion = namedtuple(
    "NextQuestion", "next_q, num_rules_found, expressions_evaluating_to_true, priority"
)


class RuleCollection:
    "A collection of rules for a particular survey"

    def __init__(self, rules=None, verbose=False):
        if rules is None:
            self.rules = []
        else:
            self.rules = rules
        self.verbose = verbose

    def __len__(self):
        return len(self.rules)

    def __getitem__(self, index):
        return self.rules[index]

    def __repr__(self):
        return f"RuleCollection(rules = {self.rules})"

    def to_dict(self):
        return [rule.to_dict() for rule in self.rules]

    @classmethod
    def from_dict(self, rule_collection_dict):
        return RuleCollection(
            rules=[Rule.from_dict(rule_dict) for rule_dict in rule_collection_dict]
        )

    def add_rule(self, rule: Rule):
        """Adds a rule to a survey. If it's not, return human-readable complaints"""
        self.rules.append(rule)

    def show_rules(self) -> None:
        if self.verbose:
            keys = ["current_q", "expression", "next_q", "priority"]
            rule_list = []
            for rule in sorted(self.rules, key=lambda r: r.current_q):
                rule_list.append({k: getattr(rule, k) for k in keys})

            print_table_with_rich(rule_list)

    def which_rules(self, q_now) -> list:
        """Which rules apply at the current node?
        More than one rule can apply. E.g., suppose we are at node 1.
        We could have three rules:
        1. "q1 == 'a' ==> 3
        2. "q1 == 'b' ==> 4
        3. "q1 == 'c' ==> 5
        """
        applicable_rules = [rule for rule in self.rules if rule.current_q == q_now]
        return applicable_rules

    def next_question(self, q_now, answers) -> int:
        "Find the next question by index, given the rule collection"
        # what rules apply at the current node?
        applicable_rules = self.which_rules(q_now)
        # Every node should have a rule - if it doesn't, there's a problem
        if not applicable_rules:
            raise SurveyRuleCollectionHasNoRulesAtNodeError

        # tracking
        expressions_evaluating_to_true = 0
        next_q = None
        highest_priority = -2  # start with -2 to 'pick up' the default rule added
        num_rules_found = 0

        for rule in applicable_rules:
            num_rules_found += 1
            try:
                if rule.evaluate(answers):  # evaluates to True
                    expressions_evaluating_to_true += 1
                    if rule.priority > highest_priority:  # higher priority
                        # we have a new champ!
                        next_q, highest_priority = rule.next_q, rule.priority
            except SurveyRuleCannotEvaluateError:
                pass

        return NextQuestion(
            next_q, num_rules_found, expressions_evaluating_to_true, highest_priority
        )

    def all_nodes_reachable(self) -> bool:
        """Are all nodes reachable, given rule set?
        To do the tree traversal, you'd have to instantiate answers to check.
        What would you do for continuous measures? Probably fork at above/below threshold?

        You could use the rules to help you draw the tree, no?
        Like you start linear
        Then take a rule, given it's conditions - figure out what options you need to track
        to build the tree e.g., if it mentions q1.answer, you need to add leafs at that node
        """
        raise NotImplementedError

    def no_cycles(self, rules: list[Rule]) -> bool:
        """Ensures there are not cycles in the rule set, which would create an infinite loop
        Probably also put a check in the Exam class to make sure they
        don't see the same question more than once - though
        that could be OK if their prompt text has changed.
        Python 3.10 has a topological sort, so
        """
        raise NotImplemented


if __name__ == "__main__":
    r = Rule(
        current_q=1,
        expression="q1 == 'yes'",
        next_q=2,
        question_name_to_index={"q1": 1},
        priority=0,
    )
