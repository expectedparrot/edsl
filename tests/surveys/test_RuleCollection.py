import unittest
import sys
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

    def test_question_name_to_index_not_duplicated_in_serialization(self):
        """Test that question_name_to_index is not redundantly stored for each rule.

        This addresses GitHub issue #2373: RuleCollection stores redundant
        question_name_to_index maps, causing O(n²) memory growth.

        The fix should store question_name_to_index once at the RuleCollection
        level rather than duplicating it in each Rule's serialized form.
        """
        num_questions = 100
        question_names = [f"q{i}" for i in range(num_questions)]
        q_name_to_idx = {name: i for i, name in enumerate(question_names)}

        # Create rules like a survey would - each rule for question i
        # references the same shared mapping
        rules = []
        for i in range(num_questions - 1):
            rule = Rule(
                current_q=i,
                expression="True",
                next_q=i + 1,
                question_name_to_index=q_name_to_idx,
                priority=-1,
            )
            rules.append(rule)

        rc = RuleCollection(num_questions=num_questions, rules=rules)

        # Serialize to dict
        rc_dict = rc.to_dict()

        # The serialized form should NOT have question_name_to_index in each rule
        # Instead, it should be stored once at the RuleCollection level
        for rule_dict in rc_dict["rules"]:
            self.assertNotIn(
                "question_name_to_index",
                rule_dict,
                "question_name_to_index should not be stored in each rule's dict"
            )

        # The mapping should be stored once at the collection level
        self.assertIn(
            "question_name_to_index",
            rc_dict,
            "question_name_to_index should be stored at the RuleCollection level"
        )
        self.assertEqual(rc_dict["question_name_to_index"], q_name_to_idx)

        # Deserialize and verify the rules still work correctly
        rc_restored = RuleCollection.from_dict(rc_dict)

        self.assertEqual(len(rc_restored), len(rc))
        self.assertEqual(rc_restored.num_questions, rc.num_questions)

        # Verify that all restored rules share the same mapping object
        # (not just equal values, but the same object reference)
        first_rule_mapping = rc_restored[0].question_name_to_index
        for rule in rc_restored[1:]:
            self.assertIs(
                rule.question_name_to_index,
                first_rule_mapping,
                "All rules should share the same question_name_to_index reference"
            )

    def test_serialization_memory_efficiency(self):
        """Test that serialization size grows linearly, not quadratically.

        With the fix, adding more questions should result in linear growth
        in serialized size, not O(n²) growth.
        """
        import json

        def create_rule_collection(num_questions):
            question_names = [f"q{i}" for i in range(num_questions)]
            q_name_to_idx = {name: i for i, name in enumerate(question_names)}

            rules = []
            for i in range(num_questions - 1):
                rule = Rule(
                    current_q=i,
                    expression="True",
                    next_q=i + 1,
                    question_name_to_index=q_name_to_idx,
                    priority=-1,
                )
                rules.append(rule)

            return RuleCollection(num_questions=num_questions, rules=rules)

        # Measure serialized sizes for different numbers of questions
        size_10 = len(json.dumps(create_rule_collection(10).to_dict()))
        size_100 = len(json.dumps(create_rule_collection(100).to_dict()))
        size_200 = len(json.dumps(create_rule_collection(200).to_dict()))

        # With O(n²) growth: size_200 / size_100 ≈ 4
        # With O(n) growth: size_200 / size_100 ≈ 2
        growth_ratio = size_200 / size_100

        # Allow some tolerance, but ratio should be closer to 2 than to 4
        self.assertLess(
            growth_ratio,
            2.5,
            f"Serialization size grew by {growth_ratio:.2f}x when doubling questions. "
            f"Expected ~2x for O(n) growth, got closer to O(n²). "
            f"Sizes: 100q={size_100}, 200q={size_200}"
        )


    def test_backward_compatibility_with_old_format(self):
        """Test that old serialized format (with question_name_to_index in each rule) still works.

        This ensures backward compatibility when loading surveys serialized before the fix.
        """
        # Simulate old format where each rule has its own question_name_to_index
        old_format_dict = {
            "rules": [
                {
                    "current_q": 0,
                    "expression": "True",
                    "next_q": 1,
                    "priority": -1,
                    "question_name_to_index": {"q0": 0, "q1": 1, "q2": 2},
                    "before_rule": False,
                },
                {
                    "current_q": 1,
                    "expression": "True",
                    "next_q": 2,
                    "priority": -1,
                    "question_name_to_index": {"q0": 0, "q1": 1, "q2": 2},
                    "before_rule": False,
                },
            ],
            "num_questions": 3,
            # No question_name_to_index at collection level (old format)
        }

        # Should load without error
        rc = RuleCollection.from_dict(old_format_dict)

        self.assertEqual(len(rc), 2)
        self.assertEqual(rc.num_questions, 3)

        # Each rule should have its mapping loaded from the per-rule dict
        self.assertEqual(rc[0].question_name_to_index, {"q0": 0, "q1": 1, "q2": 2})
        self.assertEqual(rc[1].question_name_to_index, {"q0": 0, "q1": 1, "q2": 2})


if __name__ == "__main__":
    unittest.main()
