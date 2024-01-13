from typing import List, Union
from edsl.exceptions import (
    SurveyRuleCannotEvaluateError,
    SurveyRuleCollectionHasNoRulesAtNodeError,
)
from edsl.utilities.interface import print_table_with_rich
from edsl.surveys.Rule import Rule
from edsl.surveys.base import EndOfSurvey


from collections import namedtuple

NextQuestion = namedtuple(
    "NextQuestion", "next_q, num_rules_found, expressions_evaluating_to_true, priority"
)

## We're going to need the survey object itself
## so we know how long the survey is, unless we move


class RuleCollection:
    "A collection of rules for a particular survey"

    def __init__(
        self, num_questions: int = None, rules: List[Rule] = None, verbose=False
    ):
        self.rules = rules or []
        self.num_questions = num_questions

    def __len__(self):
        return len(self.rules)

    def __getitem__(self, index):
        return self.rules[index]

    def __repr__(self):
        return f"RuleCollection(rules = {self.rules})"

    def to_dict(self):
        return {
            "rules": [rule.to_dict() for rule in self.rules],
            "num_questions": self.num_questions,
        }

    @classmethod
    def from_dict(cls, rule_collection_dict):
        rules = [
            Rule.from_dict(rule_dict) for rule_dict in rule_collection_dict["rules"]
        ]
        num_questions = rule_collection_dict["num_questions"]
        new_rc = cls(rules=rules)
        new_rc.num_questions = num_questions
        return new_rc

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

    @property
    def dag(self) -> dict:
        d = dict({})
        ## Rules are desgined at the current question and then direct where
        ## control goes next. As such, the destination nodes are the keys
        ## and the current nodes are the values. Furthermore, all questions between
        ## the current and destination nodes are also included as keys, as they will depend
        ## on the answer to the focal node as well.

        ## If we have a rule that says "if q1 == 'yes', go to q3",
        ## Then q3 depends on q1, but so does q2
        ## So the DAG would be {3: [1], 2: [1]}

        def keys_between(start_q, end_q):
            """Returns a list of all question indices between start_q and end_q"""
            if isinstance(end_q, EndOfSurvey):
                # If it's the end of the survey,
                # all questions between the start_q and the end of the survey
                # now depend on the start_q
                if self.num_questions is None:
                    raise ValueError(
                        "Cannot determine DAG when EndOfSurvey and when num_questions is not known"
                    )
                end_q = self.num_questions
            return list(range(start_q + 1, end_q))

        non_default_rules = self.non_default_rules
        for rule in non_default_rules:
            current_q = rule.current_q
            next_q = rule.next_q
            for q in keys_between(current_q, next_q + 1):
                if q in d:
                    d[q].add(current_q)
                else:
                    d[q] = set({current_q})
        return d

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
