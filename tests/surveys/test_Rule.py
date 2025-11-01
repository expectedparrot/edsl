import unittest
from edsl.surveys.exceptions import (
    SurveyRuleSkipLogicSyntaxError,
)
from edsl.questions import QuestionMultipleChoice
from edsl.surveys.rules import Rule


class TestRule(unittest.TestCase):
    def setUp(self):
        self.q1 = QuestionMultipleChoice(
            question_text="Do you like school?",
            question_options=["yes", "no"],
            question_name="like_schoool",
        )

        self.q2 = QuestionMultipleChoice(
            question_text="What is your favorite subject?",
            question_options=["math", "science", "english", "history"],
            question_name="favorite_subject",
        )

        self.question_name_to_index = {"q1": 0, "q2": 1}

    def test_invalid_expression(self):
        with self.assertRaises(SurveyRuleSkipLogicSyntaxError):
            r = Rule(
                current_q=0,
                expression="q1 == 'ye",
                next_q=1,
                question_name_to_index=self.question_name_to_index,
                priority=0,
            )

    def test_rule_refers_to_future_state(self):
        with self.assertRaises(Exception):
            r = Rule(
                current_q=0,
                expression="{{ q1.answer }} == 'yes'",
                next_q=1,
                question_name_to_index={"q1": 1},
                priority=0,
            )

    def test_rule_sends_you_backwards(self):
        with self.assertRaises(Exception):
            r = Rule(
                current_q=5,
                expression="{{ q1.answer }} == 'yes'",
                next_q=1,
                question_name_to_index=self.question_name_to_index,
                priority=0,
            )

    def test_valid_rule(self):
        try:
            r = Rule(
                current_q=0,
                expression="{{ q1.answer }} == 'yes'",
                next_q=1,
                question_name_to_index=self.question_name_to_index,
                priority=0,
            )
        except Exception as e:
            self.fail(f"Valid Rule setup raised an exception: {type(e).__name__}: {e}")


if __name__ == "__main__":
    unittest.main()
