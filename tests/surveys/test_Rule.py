import unittest
from edsl.surveys.exceptions import (
    SurveyRuleSkipLogicSyntaxError,
    SurveyRuleReferenceInRuleToUnknownQuestionError,
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

    def test_rule_references_unknown_question_single(self):
        """Test that referencing a single unknown question raises the correct exception."""
        with self.assertRaises(SurveyRuleReferenceInRuleToUnknownQuestionError) as cm:
            Rule(
                current_q=0,
                expression="{{ unknown_question.answer }} == 'yes'",
                next_q=1,
                question_name_to_index=self.question_name_to_index,
                priority=0,
            )

        # Check that the error message contains the expected information
        error_message = str(cm.exception)
        self.assertIn("unknown_question", error_message)
        self.assertIn("['unknown_question']", error_message)
        self.assertIn("Available question names", error_message)
        self.assertIn("['q1', 'q2']", error_message)

    def test_rule_references_unknown_question_multiple(self):
        """Test that referencing multiple unknown questions raises the correct exception."""
        with self.assertRaises(SurveyRuleReferenceInRuleToUnknownQuestionError) as cm:
            Rule(
                current_q=0,
                expression="{{ invalid1.answer }} == 'yes' and {{ invalid2.answer }} == 'no'",
                next_q=1,
                question_name_to_index=self.question_name_to_index,
                priority=0,
            )

        # Check that the error message contains both invalid question names
        error_message = str(cm.exception)
        self.assertIn("invalid1", error_message)
        self.assertIn("invalid2", error_message)
        self.assertIn("Available question names", error_message)

    def test_rule_references_mix_of_valid_and_invalid_questions(self):
        """Test that a rule with both valid and invalid question references raises an exception."""
        with self.assertRaises(SurveyRuleReferenceInRuleToUnknownQuestionError) as cm:
            Rule(
                current_q=1,
                expression="{{ q1.answer }} == 'yes' and {{ nonexistent.answer }} == 'no'",
                next_q=2,
                question_name_to_index=self.question_name_to_index,
                priority=0,
            )

        # Check that the error message mentions the invalid question but not the valid one
        error_message = str(cm.exception)
        self.assertIn("nonexistent", error_message)
        self.assertNotIn("q1", error_message.split("Available question names")[0])  # q1 shouldn't be in the "invalid" part

    def test_rule_with_typo_in_question_name(self):
        """Test that a rule with a typo in question name raises the correct exception."""
        with self.assertRaises(SurveyRuleReferenceInRuleToUnknownQuestionError) as cm:
            Rule(
                current_q=1,
                expression="{{ q11.answer }} == 'yes'",  # typo: q11 instead of q1
                next_q=2,
                question_name_to_index=self.question_name_to_index,
                priority=0,
            )

        # Check that the error shows the typo and available options
        error_message = str(cm.exception)
        self.assertIn("q11", error_message)
        self.assertIn("['q1', 'q2']", error_message)


if __name__ == "__main__":
    unittest.main()
