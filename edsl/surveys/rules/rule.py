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
import random
from typing import Any, Union
from collections import defaultdict


# from rich import print
from simpleeval import EvalWithCompoundTypes

from ..exceptions import SurveyError
from ..exceptions import (
    SurveyRuleCannotEvaluateError,
    SurveyRuleRefersToFutureStateError,
    SurveyRuleSendsYouBackwardsError,
    SurveyRuleSkipLogicSyntaxError,
)

from ..base import EndOfSurvey
from ...utilities import extract_variable_names, remove_edsl_version

class QuestionIndex:
    def __set_name__(self, owner, name):
        self.name = f"_{name}"

    def __get__(self, obj, objtype=None):
        return getattr(obj, self.name)

    def __set__(self, obj, value):
        if not isinstance(value, (int, EndOfSurvey.__class__)):
            raise SurveyError(f"{self.name} must be an integer or EndOfSurvey")
        if self.name == "_next_q" and isinstance(value, int):
            current_q = getattr(obj, "_current_q")
            if value <= current_q:
                raise SurveyError("next_q must be greater than current_q")
        setattr(obj, self.name, value)


class Rule:
    """The Rule class defines a "rule" for determining the next question present."""

    current_q = QuestionIndex()
    next_q = QuestionIndex()

    def __init__(
        self,
        current_q: int,
        expression: str,
        next_q: Union[int, EndOfSurvey.__class__],
        question_name_to_index: dict[str, int],
        priority: int,
        before_rule: bool = False,
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
        self.before_rule = before_rule

        if not self.next_q == EndOfSurvey:
            if self.next_q <= self.current_q:
                raise SurveyRuleSendsYouBackwardsError

        if not self.next_q == EndOfSurvey and self.current_q > self.next_q:
            raise SurveyRuleSendsYouBackwardsError(
                f"current_q: {self.current_q}, next_q: {self.next_q}"
            )

        # get the AST for the expression - used to extract the variables referenced in the expression
        try:
            self.ast_tree = ast.parse(self.expression)
        except SyntaxError:
            raise SurveyRuleSkipLogicSyntaxError(
                f"The expression {self.expression} is not valid Python syntax."
            )

        extracted_question_names = extract_variable_names(self.ast_tree)

        # make sure all the variables in the expression are known questions
        try:
            assert all([q in question_name_to_index for q in extracted_question_names])
        except AssertionError:
            pass

        # get the indices of the questions mentioned in the expression
        self.named_questions_by_index = [
            question_name_to_index[q]
            for q in extracted_question_names
            if q in question_name_to_index
        ]

        # A rule should only refer to questions that have already been asked.
        # so the named questions in the expression should not be higher than the current question
        if self.named_questions_by_index:
            if max(self.named_questions_by_index) > self.current_q:
                print(
                    "A rule refers to a future question, the answer to which would not be available here."
                )
                raise SurveyRuleRefersToFutureStateError
            
        if (referenced_questions := self._prior_question_is_in_expression()) and not self._is_jinja2_expression():            #raise ValueError("This uses the old syntax!")
            import warnings
            old_expression = self.expression
            for q in referenced_questions:
                if q + ".answer" in self.expression:
                    self.expression = self.expression.replace(q + ".answer", f"{{{{ {q}.answer }}}}")
                else:
                    self.expression = self.expression.replace(q, f"{{{{ {q}.answer }}}}")
            warnings.warn(f"This uses the old syntax! Converting to Jinja2 style with {{ }}.\nOld expression: {old_expression}\nNew expression: {self.expression}")

    def _checks(self):
        pass

    def to_dict(self, add_edsl_version=True):
        """Convert the rule to a dictionary for serialization.

        >>> r = Rule.example()
        >>> r.to_dict()
        {'current_q': 1, 'expression': "{{ q1.answer }} == 'yes'", 'next_q': 2, 'priority': 0, 'question_name_to_index': {'q1': 1}, 'before_rule': False}
        """
        return {
            "current_q": self.current_q,
            "expression": self.expression,
            "next_q": "EndOfSurvey" if self.next_q == EndOfSurvey else self.next_q,
            "priority": self.priority,
            "question_name_to_index": self.question_name_to_index,
            "before_rule": self.before_rule,
        }

    @classmethod
    @remove_edsl_version
    def from_dict(self, rule_dict):
        """Create a rule from a dictionary."""
        if rule_dict["next_q"] == "EndOfSurvey":
            rule_dict["next_q"] = EndOfSurvey

        if "before_rule" not in rule_dict:
            rule_dict["before_rule"] = False

        return Rule(
            current_q=rule_dict["current_q"],
            expression=rule_dict["expression"],
            next_q=rule_dict["next_q"],
            priority=rule_dict["priority"],
            question_name_to_index=rule_dict["question_name_to_index"],
            before_rule=rule_dict["before_rule"],
        )

    def __repr__(self):
        """Pretty-print the rule."""
        return f'Rule(current_q={self.current_q}, expression="{self.expression}", next_q={self.next_q}, priority={self.priority}, question_name_to_index={self.question_name_to_index}, before_rule={self.before_rule})'

    def __str__(self):
        """Return a string representation of the rule."""
        return self.__repr__()

    @property
    def question_index_to_name(self):
        """Reverse the dictionary do we can look up questions by name.

        >>> r = Rule.example()
        >>> r.question_index_to_name
        {1: 'q1'}

        """
        return {v: k for k, v in self.question_name_to_index.items()}

    def show_ast_tree(self):
        """Pretty-print the AST tree to the terminal.

        >>> r = Rule.example()
        >>> r.show_ast_tree()
        Module(...)
        """
        print(
            ast.dump(
                self.ast_tree, annotate_fields=True, indent=4, include_attributes=True
            )
        )

    @staticmethod
    def _prepare_replacement(current_info_env: dict[int, Any]):
        d = {}
        for var, value in current_info_env.items():
            if isinstance(value, str):
                replacement = f"'{value}'"
            else:
                replacement = str(value)
            d[var] = replacement
        return d
    
    def _prior_question_is_in_expression(self) -> set:
        """Check if the expression contains a reference to a prior question."""
        return {q for q in self.question_name_to_index.keys() if q in self.expression}
    
    def _is_jinja2_expression(self):
        """Check if the expression is a Jinja2 expression."""
        return "{{" in self.expression and "}}" in self.expression

    def evaluate(self, current_info_env: dict[int, Any]):
        """Compute the value of the expression, given a dictionary of known questions answers.

        :param current_info_env: A dictionary mapping question, scenario, and agent names to their values.

        If the expression cannot be evaluated, it raises a CannotEvaluate exception.

        >>> r = Rule.example()
        >>> r.evaluate({'q1.answer' : 'yes'})
        True
        >>> r.evaluate({'q1.answer' : 'no'})
        False

        >>> r = Rule.example(jinja2=True)
        >>> r.evaluate({'q1.answer' : 'yes'})
        True

        >>> r = Rule.example(jinja2=True)
        >>> r.evaluate({'q1.answer' : 'This is q1'})
        False

        >>> import warnings
        >>> with warnings.catch_warnings(record=True) as w:
        ...     expression = "q1 == 'yes'"
        ...     r = Rule(current_q=1, expression=expression, next_q=2, question_name_to_index={"q1": 1}, priority=0)
        ...     result = r.evaluate({'q1.answer' : 'yes'})
        ...     assert len(w) == 1  # Verify warning was issued
        ...     assert result == True
        """
        from jinja2 import Template

        def jinja_ize_dictionary(dictionary):
            """Convert a dictionary to a Jinja2 dictionary.
            
            Keys must be either:
            - 'agent'
            - 'scenario'
            - A valid question name from question_name_to_index
            
            For question keys, the value is wrapped in an 'answer' subdictionary.
            
            Examples:
            >>> d = jinja_ize_dictionary({'q1': 'yes'}, {'q1': 1})
            >>> d['q1']['answer']
            'yes'
            
            >>> d = jinja_ize_dictionary({'agent': 'friendly'}, {'q1': 1})
            >>> d['agent']
            'friendly'            
            """
            jinja_dict = defaultdict(dict)
            
            for key, value in dictionary.items():
                # print("Now processing key: ", key)
                # print(f"key: {key}, value: {value}")
                # Handle special keys
                if 'agent.' in key:
                    # print("Agent key found")
                    jinja_dict['agent'][key.split('.')[1]] = value
                    # print("jinja dict: ", jinja_dict)
                    continue 

                if 'scenario.' in key:
                    # print("Scenario key found")
                    jinja_dict['scenario'][key.split('.')[1]] = value
                    # print("jinja dict: ", jinja_dict)
                    continue

                # print("On to question keys")
                for question_name in self.question_name_to_index.keys():
                    # print("question_name: ", question_name)
                    if question_name in key:
                        if question_name == key:
                            # print("question name is key; it's an answer")
                            jinja_dict[question_name]['answer'] = value
                            # print("jinja dict: ", jinja_dict)
                            continue
                        else:
                            # print("question name is not key; it's a sub-type")
                            if "." in key:
                                passed_name, value_type = key.split('.')
                                # print("passed_name: ", passed_name)
                                # print("value_type: ", value_type)
                                if passed_name == question_name:
                                    # print("passed name is question name; it's a sub-type")
                                    jinja_dict[question_name][value_type] = value
                                    # print("jinja dict: ", jinja_dict)
                                    continue
                  
            return jinja_dict

        def substitute_in_answers(expression, current_info_env):
            """Take the dictionary of answers and substitute them into the expression."""

            current_info = self._prepare_replacement(current_info_env)

            if "{{" in expression and "}}" in expression:
                template_expression = Template(self.expression)
                jinja_dict = jinja_ize_dictionary(current_info)
                to_evaluate = template_expression.render(jinja_dict)
            else:
                to_evaluate = expression
                for var, value in current_info.items():
                    to_evaluate = to_evaluate.replace(var, value)

            return to_evaluate
        
        #breakpoint()

        try:
            to_evaluate = substitute_in_answers(self.expression, current_info_env)
        except Exception as e:
            msg = f"""Exception in evaluation: {e}. The expression is: {self.expression}. The current info env trying to substitute in is: {current_info_env}. After the substition, the expression was: {to_evaluate}."""
            raise SurveyRuleCannotEvaluateError(msg)

        random_functions = {
            "randint": random.randint,
            "choice": random.choice,
            "random": random.random,
            "uniform": random.uniform,
            # Add any other random functions you want to allow
        }

        try:
            return EvalWithCompoundTypes(functions=random_functions).eval(to_evaluate)
        except Exception as e:
            msg = f"""Exception in evaluation: {e}. The expression is: {self.expression}. The current info env trying to substitute in is: {current_info_env}. After the substition, the expression was: {to_evaluate}."""
            raise SurveyRuleCannotEvaluateError(msg)

    @classmethod
    def example(cls, jinja2=False, bad=False):
        if jinja2:
            # a rule written in jinja2 style with {{ }}
            expression = "{{ q1.answer }} == 'yes'"
        else:
            expression = "{{ q1.answer }} == 'yes'"

        if bad and jinja2:
            # a rule written in jinja2 style with {{ }} but with a 'bad' expression
            expression = "{{ q1 }} == 'This is q1'"

        if bad and not jinja2:
            expression = "{{ q1.answer }} == 'This is q1'"

        r = Rule(
            current_q=1,
            expression=expression,
            next_q=2,
            question_name_to_index={"q1": 1},
            priority=0,
        )
        return r


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
