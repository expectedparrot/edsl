"""A collection of rules for a survey."""

from typing import List, Any, Optional
from collections import defaultdict, UserList, namedtuple

from ..exceptions import (
    SurveyRuleCannotEvaluateError,
    SurveyRuleCollectionHasNoRulesAtNodeError,
)

from .rule import Rule
from ..base import EndOfSurvey
from ..dag import DAG

NextQuestion = namedtuple(
    "NextQuestion", "next_q, num_rules_found, expressions_evaluating_to_true, priority"
)


class RuleCollection(UserList):
    """A collection of rules for a particular survey."""

    def __init__(self, num_questions: Optional[int] = None, rules: List[Rule] = None):
        """Initialize the RuleCollection object.

        :param num_questions: The number of questions in the survey.
        :param rules: A list of Rule objects.
        """
        super().__init__(rules or [])
        self.num_questions = num_questions

    def __repr__(self):
        """Return a string representation of the RuleCollection object.

        Example usage:

        .. code-block:: python

            rule_collection = RuleCollection.example()
            _ = eval(repr(rule_collection))

        """
        return f"RuleCollection(rules={self.data}, num_questions={self.num_questions})"

    def to_dataset(self):
        """Return a Dataset object representation of the RuleCollection object."""
        from ...dataset import Dataset

        keys = ["current_q", "expression", "next_q", "priority", "before_rule"]
        rule_list = {}
        for rule in sorted(self, key=lambda r: r.current_q):
            for k in keys:
                rule_list.setdefault(k, []).append(getattr(rule, k))

        return Dataset([{k: v} for k, v in rule_list.items()])

    def _repr_html_(self):
        """Return an HTML representation of the RuleCollection object.
        
        >>> rule_collection = RuleCollection.example()
        >>> _ = rule_collection._repr_html_()
        """
        return self.to_dataset()._repr_html_()

    def to_dict(self, add_edsl_version=True):
        """Create a dictionary representation of the RuleCollection object.
        >>> rule_collection = RuleCollection.example()
        >>> rule_collection_dict = rule_collection.to_dict()
        >>> new_rule_collection = RuleCollection.from_dict(rule_collection_dict)
        >>> repr(new_rule_collection) == repr(rule_collection)
        True
        """
        return {
            "rules": [rule.to_dict() for rule in self],
            "num_questions": self.num_questions,
        }

    @classmethod
    def from_dict(cls, rule_collection_dict):
        """Create a RuleCollection object from a dictionary.

        >>> rule_collection = RuleCollection.example()
        >>> rule_collection_dict = rule_collection.to_dict()
        >>> new_rule_collection = RuleCollection.from_dict(rule_collection_dict)
        >>> repr(new_rule_collection) == repr(rule_collection)
        True
        """
        rules = [
            Rule.from_dict(rule_dict) for rule_dict in rule_collection_dict["rules"]
        ]
        num_questions = rule_collection_dict["num_questions"]
        new_rc = cls(rules=rules)
        new_rc.num_questions = num_questions
        return new_rc

    def add_rule(self, rule: Rule) -> None:
        """Add a rule to a survey.

        >>> rule_collection = RuleCollection()
        >>> rule_collection.add_rule(Rule(current_q=1, expression="q1 == 'yes'", next_q=3, priority=1, question_name_to_index={'q1': 1, 'q2': 2, 'q3': 3, 'q4': 4}))
        >>> len(rule_collection)
        1

        >>> rule_collection = RuleCollection()
        >>> r = Rule(current_q=1, expression="True", next_q=3, priority=1, question_name_to_index={'q1': 1, 'q2': 2, 'q3': 3, 'q4': 4}, before_rule = True)
        >>> rule_collection.add_rule(r)
        >>> rule_collection[0] == r
        True
        >>> len(rule_collection.applicable_rules(1, before_rule=True))
        1
        >>> len(rule_collection.applicable_rules(1, before_rule=False))
        0
        """
        self.append(rule)

    def show_rules(self) -> None:
        """Print the rules in a table.
        """
        return self.to_dataset()

    def skip_question_before_running(self, q_now: int, answers: dict[str, Any]) -> bool:
        """Determine if a question should be skipped before running the question.

        :param q_now: The current question index.
        :param answers: The answers to the survey questions.

        >>> rule_collection = RuleCollection()
        >>> r = Rule(current_q=1, expression="True", next_q=2, priority=1, question_name_to_index={}, before_rule = True)
        >>> rule_collection.add_rule(r)
        >>> rule_collection.skip_question_before_running(1, {})
        True

        >>> rule_collection = RuleCollection()
        >>> r = Rule(current_q=1, expression="False", next_q=2, priority=1, question_name_to_index={}, before_rule = True)
        >>> rule_collection.add_rule(r)
        >>> rule_collection.skip_question_before_running(1, {})
        False
        """
        for rule in self.applicable_rules(q_now, before_rule=True):
            if rule.evaluate(answers):
                return True
        return False

    def applicable_rules(self, q_now: int, before_rule: bool = False) -> list:
        """Show the rules that apply at the current node.

        :param q_now: The current question index.
        :param before_rule: If True, return rules that are of the type that apply before the question is asked.

        Example usage:

        >>> rule_collection = RuleCollection.example()
        >>> rule_collection.applicable_rules(1)
        [Rule(current_q=1, expression="{{ q1.answer }} == 'yes'", next_q=3, priority=1, question_name_to_index={'q1': 1, 'q2': 2, 'q3': 3, 'q4': 4}, before_rule=False), Rule(current_q=1, expression="{{ q1.answer }} == 'no'", next_q=2, priority=1, question_name_to_index={'q1': 1, 'q2': 2, 'q3': 3, 'q4': 4}, before_rule=False)]

        The default is that the rule is applied after the question is asked.
        If we want to see the rules that apply before the question is asked, we can set before_rule=True.

        .. code-block:: python

            rule_collection = RuleCollection.example()
            rule_collection.applicable_rules(1)
            [Rule(current_q=1, expression="q1 == 'yes'", next_q=3, priority=1, question_name_to_index={'q1': 1, 'q2': 2, 'q3': 3, 'q4': 4}), Rule(current_q=1, expression="q1 == 'no'", next_q=2, priority=1, question_name_to_index={'q1': 1, 'q2': 2, 'q3': 3, 'q4': 4})]

        More than one rule can apply. For example, suppose we are at node 1.
        We could have three rules:
        1. "q1 == 'a' ==> 3
        2. "q1 == 'b' ==> 4
        3. "q1 == 'c' ==> 5
        """
        return [
            rule
            for rule in self
            if rule.current_q == q_now and rule.before_rule == before_rule
        ]

    def next_question(self, q_now: int, answers: dict[str, Any]) -> NextQuestion:
        """Find the next question by index, given the rule collection.

        This rule is applied after the question is answered.

        :param q_now: The current question index.
        :param answers: The answers to the survey questions so far, including the current question.

        >>> rule_collection = RuleCollection.example()
        >>> rule_collection.next_question(1, {'q1.answer': 'yes'})
        NextQuestion(next_q=3, num_rules_found=2, expressions_evaluating_to_true=1, priority=1)

        """
        expressions_evaluating_to_true = 0
        next_q = None
        highest_priority = -2  # start with -2 to 'pick up' the default rule added
        num_rules_found = 0

        for rule in self.applicable_rules(q_now, before_rule=False):
            num_rules_found += 1
            try:
                if rule.evaluate(answers):  # evaluates to True
                    expressions_evaluating_to_true += 1
                    if rule.priority > highest_priority:  # higher priority
                        # we have a new champ!
                        next_q, highest_priority = rule.next_q, rule.priority
            except SurveyRuleCannotEvaluateError:
                raise

        if num_rules_found == 0:
            raise SurveyRuleCollectionHasNoRulesAtNodeError(
                f"No rules found for question {q_now}"
            )

        ## Now we need to check if the *next question* has any 'before; rules that we should follow
        for rule in self.applicable_rules(next_q, before_rule=True):
            if rule.evaluate(answers):  # rule evaluates to True
                return self.next_question(next_q, answers)

        return NextQuestion(
            next_q, num_rules_found, expressions_evaluating_to_true, highest_priority
        )

    @property
    def non_default_rules(self) -> List[Rule]:
        """Return all rules that are not the default rule.

        >>> rule_collection = RuleCollection.example()
        >>> len(rule_collection.non_default_rules)
        2

        Example usage:

        .. code-block:: python

            rule_collection = RuleCollection.example()
            len(rule_collection.non_default_rules)
            2

        """
        return [rule for rule in self if rule.priority > -1]

    def keys_between(self, start_q, end_q, right_inclusive=True):
        """Return a list of all question indices between start_q and end_q.

        Example usage:

        .. code-block:: python

            rule_collection = RuleCollection(num_questions=5)
            rule_collection.keys_between(1, 3)
            [2, 3]
            rule_collection.keys_between(1, 4)
            [2, 3, 4]
            rule_collection.keys_between(1, EndOfSurvey, right_inclusive=False)
            [2, 3]

        """
        # If it's the end of the survey, all questions between the start_q and the end of the survey now depend on the start_q
        if end_q == EndOfSurvey:
            if self.num_questions is None:
                raise ValueError(
                    "Cannot determine DAG when EndOfSurvey and when num_questions is not known."
                )
            end_q = self.num_questions - 1

        question_range = list(range(start_q + 1, end_q + int(right_inclusive)))

        return question_range

    @property
    def dag(self) -> dict:
        """
        Find the DAG of the survey, based on the skip logic.

        Keys are children questions; the list of values are nodes that must be answered first

        Rules are designated at the current question and then direct where
        control goes next. As such, the destination nodes are the keys
        and the current nodes are the values. Furthermore, all questions between
        the current and destination nodes are also included as keys, as they will depend
        on the answer to the focal node as well.

        For exmaple, if we have a rule that says "if q1 == 'yes', go to q3", then q3 depends on q1, but so does q2.
        So the DAG would be {3: [1], 2: [1]}.

        Example usage:

        .. code-block:: python

            rule_collection = RuleCollection(num_questions=5)
            qn2i = {'q1': 1, 'q2': 2, 'q3': 3, 'q4': 4}
            rule_collection.add_rule(Rule(current_q=1, expression="q1 == 'yes'", next_q=3, priority=1,  question_name_to_index = qn2i))
            rule_collection.add_rule(Rule(current_q=1, expression="q1 == 'no'", next_q=2, priority=1, question_name_to_index = qn2i))
            rule_collection.dag
            {2: {1}, 3: {1}}

        """
        children_to_parents = defaultdict(set)
        # We are only interested in non-default rules. Default rules are those
        # that just go to the next question, so they don't add any dependencies

        ## I think for a skip-question, the potenially-skippable question
        ## depends on all the other questions bein answered first.
        for rule in self.non_default_rules:
            if not rule.before_rule:
                # for a regular rule, the next question depends on the current question answer
                current_q, next_q = rule.current_q, rule.next_q
                for q in self.keys_between(current_q, next_q):
                    children_to_parents[q].add(current_q)
            else:
                # for the 'before rule' skipping depends on all previous answers.
                focal_q = rule.current_q
                for q in range(0, focal_q):
                    children_to_parents[focal_q].add(q)

        return DAG(dict(sorted(children_to_parents.items())))

    def detect_cycles(self):
        """
        Detect cycles in the survey rules using depth-first search.

        :return: A list of cycles if any are found, otherwise an empty list.
        """
        dag = self.dag
        visited = set()
        path = []
        cycles = []

        def dfs(node):
            if node in path:
                cycle = path[path.index(node) :]
                cycles.append(cycle + [node])
                return

            if node in visited:
                return

            visited.add(node)
            path.append(node)

            for child in dag.get(node, []):
                dfs(child)

            path.pop()

        for node in dag:
            if node not in visited:
                dfs(node)

        return cycles

    @classmethod
    def example(cls):
        """Create an example RuleCollection object."""
        qn2i = {"q1": 1, "q2": 2, "q3": 3, "q4": 4}
        return cls(
            num_questions=5,
            rules=[
                Rule(
                    current_q=1,
                    expression="{{ q1.answer }} == 'yes'",
                    next_q=3,
                    priority=1,
                    question_name_to_index=qn2i,
                ),
                Rule(
                    current_q=1,
                    expression="{{ q1.answer }} == 'no'",
                    next_q=2,
                    priority=1,
                    question_name_to_index=qn2i,
                ),
            ],
        )


if __name__ == "__main__":
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)
