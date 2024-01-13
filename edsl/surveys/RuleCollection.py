from typing import List
from edsl.exceptions import (
    SurveyRuleCannotEvaluateError,
    SurveyRuleCollectionHasNoRulesAtNodeError,
)
from edsl.utilities.interface import print_table_with_rich
from edsl.surveys.Rule import Rule

from collections import namedtuple

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

    @property
    def non_default_rules(self) -> List[Rule]:
        """Returns all rules that are not the default rule"""
        return [rule for rule in self.rules if rule.priority > -1]

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
