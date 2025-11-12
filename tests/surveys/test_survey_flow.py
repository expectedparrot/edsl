"""Tests for Survey flow navigation and instruction handling."""

import unittest
from edsl.surveys.survey import Survey
from edsl.surveys.base import EndOfSurvey
from edsl.questions import QuestionMultipleChoice, QuestionFreeText
from edsl.instructions import Instruction
from edsl.surveys.exceptions import SurveyError


class TestSurveyFlow(unittest.TestCase):
    """Test cases for survey flow navigation including instructions."""

    def setUp(self):
        """Set up test surveys for different scenarios."""
        # Create basic questions
        self.q0 = QuestionMultipleChoice(
            question_text="Do you like school?",
            question_options=["yes", "no"],
            question_name="q0",
        )
        self.q1 = QuestionMultipleChoice(
            question_text="Why not?",
            question_options=["killer bees in cafeteria", "other"],
            question_name="q1",
        )
        self.q2 = QuestionMultipleChoice(
            question_text="Why?",
            question_options=["**lack*** of killer bees in cafeteria", "other"],
            question_name="q2",
        )
        self.q3 = QuestionFreeText(
            question_text="Any additional comments?",
            question_name="q3",
        )

        # Create instructions
        self.intro_instruction = Instruction(
            text="Welcome! Please answer the following questions honestly.",
            name="intro",
        )
        self.middle_instruction = Instruction(
            text="Now we'll ask some follow-up questions.", name="middle"
        )
        self.end_instruction = Instruction(
            text="Thank you for your detailed responses!", name="end"
        )

    def test_next_question_basic_functionality(self):
        """Test that next_question_with_instructions works like next_question for surveys without instructions."""
        # Create survey without instructions
        survey = Survey([self.q0, self.q1, self.q2])
        survey = survey.add_rule(self.q0, "{{ q0.answer }} == 'yes'", self.q2)

        # Compare with original next_question method
        original_first = survey.next_question()
        new_first = survey.next_question_with_instructions()
        self.assertEqual(original_first.question_name, new_first.question_name)

        # Test with answers
        original_yes = survey.next_question("q0", {"q0.answer": "yes"})
        new_yes = survey.next_question_with_instructions("q0", {"q0.answer": "yes"})
        self.assertEqual(original_yes.question_name, new_yes.question_name)

        original_no = survey.next_question("q0", {"q0.answer": "no"})
        new_no = survey.next_question_with_instructions("q0", {"q0.answer": "no"})
        self.assertEqual(original_no.question_name, new_no.question_name)

    def test_single_instruction_at_beginning(self):
        """Test survey with a single instruction at the beginning."""
        survey = Survey([self.intro_instruction, self.q0, self.q1, self.q2])
        survey = survey.add_rule(self.q0, "{{ q0.answer }} == 'yes'", self.q2)

        # First item should be the instruction
        first_item = survey.next_question_with_instructions()
        self.assertEqual(first_item.name, "intro")
        self.assertTrue(hasattr(first_item, "text"))
        self.assertFalse(hasattr(first_item, "question_name"))

        # After instruction should be first question
        second_item = survey.next_question_with_instructions(first_item)
        self.assertEqual(second_item.question_name, "q0")

        # Test rule logic still works
        third_item = survey.next_question_with_instructions(
            second_item, {"q0.answer": "yes"}
        )
        self.assertEqual(third_item.question_name, "q2")

    def test_multiple_instructions_different_positions(self):
        """Test survey with instructions at different positions."""
        # Create survey: intro -> q0 -> middle -> q1 -> q2 -> end -> q3
        survey = Survey()
        survey = survey.add_instruction(self.intro_instruction)
        survey = survey.add_question(self.q0)
        survey = survey.add_instruction(self.middle_instruction)
        survey = survey.add_question(self.q1)
        survey = survey.add_question(self.q2)
        survey = survey.add_instruction(self.end_instruction)
        survey = survey.add_question(self.q3)

        # Verify the order
        combined_items = survey._recombined_questions_and_instructions()
        expected_names = ["intro", "q0", "middle", "q1", "q2", "end", "q3"]
        actual_names = [item.name for item in combined_items]
        self.assertEqual(actual_names, expected_names)

        # Test step-by-step progression
        current = None
        expected_sequence = ["intro", "q0", "middle", "q1", "q2", "end", "q3"]

        for i, expected_name in enumerate(expected_sequence):
            current = survey.next_question_with_instructions(current)
            self.assertEqual(
                current.name,
                expected_name,
                f"Step {i}: expected {expected_name}, got {current.name}",
            )

        # Next step should be EndOfSurvey
        end_result = survey.next_question_with_instructions(current)
        self.assertEqual(end_result, EndOfSurvey)

    def test_instructions_with_rule_jumps(self):
        """Test that instructions are properly handled when rules cause jumps."""
        # Create survey: q0 -> instruction -> q1 -> q2
        # Add rule: if q0 == 'yes', jump to q2 (should show instruction first)
        survey = Survey()
        survey = survey.add_question(self.q0)
        survey = survey.add_instruction(self.middle_instruction)  # Between q0 and q1
        survey = survey.add_question(self.q1)
        survey = survey.add_question(self.q2)

        # Add rule to jump from q0 to q2 on 'yes'
        survey = survey.add_rule(self.q0, "{{ q0.answer }} == 'yes'", self.q2)

        # When answering 'yes' to q0, should hit the instruction before q2
        next_item = survey.next_question_with_instructions("q0", {"q0.answer": "yes"})
        self.assertEqual(next_item.name, "middle")

        # After the instruction, should get q2 (need to pass answer context)
        after_instruction = survey.next_question_with_instructions(
            next_item, {"q0.answer": "yes"}
        )
        self.assertEqual(after_instruction.question_name, "q2")

        # When answering 'no' to q0, should go to instruction then q1
        next_item_no = survey.next_question_with_instructions("q0", {"q0.answer": "no"})
        self.assertEqual(next_item_no.name, "middle")

        after_instruction_no = survey.next_question_with_instructions(
            next_item_no, {"q0.answer": "no"}
        )
        self.assertEqual(after_instruction_no.question_name, "q1")

    def test_instruction_between_rule_jump_targets(self):
        """Test instruction placement between questions that are rule jump targets."""
        # Create survey: q0 -> q1 -> instruction -> q2
        # Add rule: q0 with 'yes' jumps to q2 (should show instruction first)
        survey = Survey([self.q0, self.q1])
        survey = survey.add_instruction(
            self.middle_instruction
        )  # This should get index 1.5
        survey = survey.add_question(self.q2)

        # Add rule to jump from q0 to q2 on 'yes'
        survey = survey.add_rule(self.q0, "{{ q0.answer }} == 'yes'", self.q2)

        # Check pseudo indices
        pseudo_indices = survey._pseudo_indices
        self.assertEqual(pseudo_indices["q0"], 0)
        self.assertEqual(pseudo_indices["q1"], 1)
        self.assertEqual(pseudo_indices["middle"], 1.5)
        self.assertEqual(pseudo_indices["q2"], 2)

        # When jumping from q0 to q2 with 'yes', should hit instruction first
        next_item = survey.next_question_with_instructions("q0", {"q0.answer": "yes"})
        self.assertEqual(next_item.name, "middle")

        # After instruction, should get q2
        after_instruction = survey.next_question_with_instructions(next_item)
        self.assertEqual(after_instruction.question_name, "q2")

    def test_string_input_handling(self):
        """Test that string inputs work for both questions and instructions."""
        survey = Survey([self.intro_instruction, self.q0, self.q1])

        # Test string input for instruction
        next_from_intro = survey.next_question_with_instructions("intro")
        self.assertEqual(next_from_intro.question_name, "q0")

        # Test string input for question
        next_from_q0 = survey.next_question_with_instructions("q0")
        self.assertEqual(next_from_q0.question_name, "q1")

    def test_error_handling(self):
        """Test error handling for invalid inputs."""
        survey = Survey([self.q0, self.q1])

        # Test with invalid item name
        with self.assertRaises(SurveyError):
            survey.next_question_with_instructions("nonexistent")

        # Test with survey that has no rules (should still work for instructions)
        survey_no_rules = Survey([self.intro_instruction])
        first = survey_no_rules.next_question_with_instructions()
        self.assertEqual(first.name, "intro")

        # Should reach end after instruction
        end_result = survey_no_rules.next_question_with_instructions(first)
        self.assertEqual(end_result, EndOfSurvey)

    def test_complex_multi_instruction_flow(self):
        """Test a complex survey with multiple instructions and rules."""
        # Create complex survey: intro -> q0 -> middle1 -> q1 -> middle2 -> q2 -> end -> q3
        survey = Survey()
        survey = survey.add_instruction(self.intro_instruction)
        survey = survey.add_question(self.q0)

        middle1 = Instruction(text="Section 1 complete", name="middle1")
        survey = survey.add_instruction(middle1)
        survey = survey.add_question(self.q1)

        middle2 = Instruction(text="Section 2 starting", name="middle2")
        survey = survey.add_instruction(middle2)
        survey = survey.add_question(self.q2)
        survey = survey.add_instruction(self.end_instruction)
        survey = survey.add_question(self.q3)

        # Add complex rules
        survey = survey.add_rule(
            self.q0, "{{ q0.answer }} == 'yes'", self.q2
        )  # Skip q1
        # Note: We skip the q1 rule since q1 will be skipped and won't have an answer

        # Test path when q0 = 'yes' (should skip q1 but show all relevant instructions)
        current = None
        path = []
        answers = {}

        for _ in range(10):  # Prevent infinite loops
            current = survey.next_question_with_instructions(current, answers)
            if current == EndOfSurvey:
                path.append("EndOfSurvey")
                break

            path.append(current.name)

            # Simulate answering
            if hasattr(current, "question_name"):
                if current.question_name == "q0":
                    answers["q0.answer"] = "yes"
                elif current.question_name == "q2":
                    answers["q2.answer"] = "some answer"
                elif current.question_name == "q3":
                    answers["q3.answer"] = "final answer"

        # Expected path: intro -> q0 -> middle1 -> middle2 -> q2 -> end -> q3 -> EndOfSurvey
        # (Should skip q1 due to rule, but show instructions in order)
        expected_path = [
            "intro",
            "q0",
            "middle1",
            "middle2",
            "q2",
            "end",
            "q3",
            "EndOfSurvey",
        ]
        self.assertEqual(path, expected_path)

    def test_instruction_only_survey(self):
        """Test a survey that contains only instructions."""
        instruction1 = Instruction(text="First instruction", name="inst1")
        instruction2 = Instruction(text="Second instruction", name="inst2")

        survey = Survey([instruction1, instruction2])

        # First item
        first = survey.next_question_with_instructions()
        self.assertEqual(first.name, "inst1")

        # Second item
        second = survey.next_question_with_instructions(first)
        self.assertEqual(second.name, "inst2")

        # Should end after second instruction
        end_result = survey.next_question_with_instructions(second)
        self.assertEqual(end_result, EndOfSurvey)

    def test_last_item_instruction_survey(self):
        """Test a survey that contains only instructions."""
        instruction1 = Instruction(
            name="introduction",
            text="Welcome to the survey. Please think about the following question carefully.",
        )
        question = QuestionMultipleChoice(
            question_name="thoughts_on_activity",
            question_text="What are your thoughts on tennis?",
            question_options=["I love it", "I hate it", "I'm neutral"],
        )
        instruction2 = Instruction(
            name="conclusion",
            text="Thank you for your time!",
        )

        survey = Survey(questions=[instruction1, question, instruction2])

        # First item
        first = survey.next_question_with_instructions()
        self.assertEqual(first.name, "introduction")

        # Second item
        second = survey.next_question_with_instructions(first)
        self.assertEqual(second.question_name, "thoughts_on_activity")

        # Third item
        third = survey.next_question_with_instructions(second)
        self.assertEqual(third.name, "conclusion")

        # Should end after third item
        end_result = survey.next_question_with_instructions(third)
        self.assertEqual(end_result, EndOfSurvey)

    def test_skip_rule_basic(self):
        """Test that skip rules work with next_question_with_instructions."""
        survey = Survey([self.q0, self.q1, self.q2])

        # Add skip rule: skip q1 if q0.answer == 'yes'
        survey = survey.add_skip_rule(self.q1, "{{ q0.answer }} == 'yes'")

        # Start with q0
        current = survey.next_question_with_instructions()
        self.assertEqual(current.question_name, "q0")

        # After answering 'yes' to q0, q1 should be skipped, so we get q2
        next_item = survey.next_question_with_instructions(
            current, {"q0.answer": "yes"}
        )
        self.assertEqual(next_item.question_name, "q2")

        # After answering 'no' to q0, q1 should NOT be skipped, so we get q1
        next_item_no = survey.next_question_with_instructions(
            current, {"q0.answer": "no"}
        )
        self.assertEqual(next_item_no.question_name, "q1")

    def test_empty_survey(self):
        """Test behavior with an empty survey."""
        survey = Survey([])

        # Should return EndOfSurvey immediately
        result = survey.next_question_with_instructions()
        self.assertEqual(result, EndOfSurvey)


if __name__ == "__main__":
    unittest.main()
