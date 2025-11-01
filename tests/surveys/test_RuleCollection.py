import unittest
from edsl.surveys.exceptions import SurveyRuleCollectionHasNoRulesAtNodeError
from edsl.surveys.rules import Rule, RuleCollection


class TestRuleCollection(unittest.TestCase):
    def test_next_question_with_no_rules(self):
        rc = RuleCollection()
        with self.assertRaises(SurveyRuleCollectionHasNoRulesAtNodeError):
            rc.next_question(None, None)

    def test_add_rule_and_query_rules(self):
        rc = RuleCollection()

        rule = Rule(
            current_q=0,
            expression="{{ q1.answer }} == 'yes'",
            next_q=1,
            question_name_to_index={"q1": 0},
            priority=1,
        )

        rc.add_rule(rule)

        # Assert that no rules apply for an irrelevant question index
        self.assertEqual(rc.applicable_rules(4), [])

        # Assert that rules do apply for the relevant question index
        rules_that_apply = rc.applicable_rules(0)
        self.assertEqual(len(rules_that_apply), 1)
        self.assertEqual(rules_that_apply[0].priority, 1)

    def test_dag(self):
        rc = RuleCollection()

        rule = Rule(
            current_q=0,
            expression="{{ q1.answer }} == 'yes'",
            next_q=1,
            question_name_to_index={"q1": 0},
            priority=1,
        )

        rc.add_rule(rule)
        # print(rc.non_default_rules)

        print(rc.dag)
        # breakpoint()


if __name__ == "__main__":
    unittest.main()
