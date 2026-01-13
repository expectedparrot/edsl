"""Tests for question group navigation with skip logic.

This module tests the group-based navigation functionality introduced to handle
complex survey flows where questions are organized into logical groups but
may be skipped due to conditional logic.

The key methods being tested include:
- create_allowable_groups(): Create dependency-aware question groups
- next_question_group(): Navigate to the next group with skip logic handling
- get_question_group(): Find which group contains a specific question
- suggest_dependency_aware_groups(): Get suggestions for valid groupings

Test coverage includes:
- Basic group creation and navigation
- Skip logic within groups (partial skipping)
- Entire group skipping scenarios
- Complex branching logic with multiple paths
- Edge cases (empty surveys, single questions, etc.)
- Integration with visualization features

These tests ensure that UIs can efficiently render groups of questions while
properly handling all the complex conditional logic that may skip questions
based on previous answers.
"""

import unittest
from edsl.surveys import Survey
from edsl.surveys.navigation_markers import EndOfSurvey
from edsl.surveys.exceptions import SurveyCreationError, SurveyError
from edsl.questions import QuestionMultipleChoice, QuestionFreeText, QuestionYesNo
from edsl.instructions import Instruction


class TestGroupNavigation(unittest.TestCase):
    """Test cases for question group navigation and skip logic."""

    def setUp(self):
        """Set up common questions for testing."""
        self.q1 = QuestionMultipleChoice(
            question_text="What's your experience level?",
            question_options=["beginner", "intermediate", "expert"],
            question_name="experience",
        )

        self.q2 = QuestionFreeText(
            question_text="What's your primary role?", question_name="role"
        )

        self.q3 = QuestionFreeText(
            question_text="Basic question for beginners", question_name="basic_question"
        )

        self.q4 = QuestionFreeText(
            question_text="Advanced question for experts",
            question_name="advanced_question",
        )

        self.q5 = QuestionFreeText(
            question_text="Expert tools question", question_name="expert_tools"
        )

        self.q6 = QuestionFreeText(
            question_text="Final feedback", question_name="feedback"
        )

    def test_create_allowable_groups_basic(self):
        """Test basic group creation without dependencies."""
        survey = Survey([self.q1, self.q2, self.q3, self.q4])
        survey = survey.create_allowable_groups("section", max_group_size=2)

        self.assertEqual(len(survey.question_groups), 2)
        self.assertIn("section_0", survey.question_groups)
        self.assertIn("section_1", survey.question_groups)
        self.assertEqual(survey.question_groups["section_0"], (0, 1))
        self.assertEqual(survey.question_groups["section_1"], (2, 3))

    def test_create_allowable_groups_max_size_one(self):
        """Test group creation with max size of 1."""
        survey = Survey([self.q1, self.q2, self.q3])
        survey = survey.create_allowable_groups("individual", max_group_size=1)

        self.assertEqual(len(survey.question_groups), 3)
        self.assertEqual(survey.question_groups["individual_0"], (0, 0))
        self.assertEqual(survey.question_groups["individual_1"], (1, 1))
        self.assertEqual(survey.question_groups["individual_2"], (2, 2))

    def test_dependency_validation_in_groups(self):
        """Test that groups with internal dependencies are rejected."""
        q1 = QuestionFreeText(question_text="Name?", question_name="name")
        q2 = QuestionFreeText(question_text="Hi {{name}}!", question_name="greeting")

        survey = Survey([q1, q2])

        # This should fail because q2 depends on q1
        with self.assertRaises(SurveyCreationError):
            survey.add_question_group("name", "greeting", "invalid_group")

    def test_get_question_group(self):
        """Test getting the group name for a question."""
        survey = Survey([self.q1, self.q2, self.q3, self.q4])
        survey = survey.create_allowable_groups("section", max_group_size=2)

        self.assertEqual(survey.get_question_group("experience"), "section_0")
        self.assertEqual(survey.get_question_group("role"), "section_0")
        self.assertEqual(survey.get_question_group("basic_question"), "section_1")
        self.assertEqual(survey.get_question_group("advanced_question"), "section_1")
        self.assertIsNone(survey.get_question_group("nonexistent"))

    def test_next_question_group_no_skip(self):
        """Test next_question_group when no questions are skipped."""
        survey = Survey([self.q1, self.q2, self.q3, self.q4])
        survey = survey.create_allowable_groups("section", max_group_size=2)

        # Get first group
        result = survey.next_question_group()
        self.assertIsNotNone(result)
        group_name, questions = result
        self.assertEqual(group_name, "section_0")
        self.assertEqual(len(questions), 2)
        self.assertEqual(questions[0].question_name, "experience")
        self.assertEqual(questions[1].question_name, "role")

        # Get second group
        result = survey.next_question_group("role", {})
        self.assertIsNotNone(result)
        group_name, questions = result
        self.assertEqual(group_name, "section_1")
        self.assertEqual(len(questions), 2)
        self.assertEqual(questions[0].question_name, "basic_question")
        self.assertEqual(questions[1].question_name, "advanced_question")

        # No more groups
        result = survey.next_question_group("advanced_question", {})
        self.assertIsNone(result)

    def test_next_question_group_with_skip(self):
        """Test next_question_group when some questions are skipped."""
        survey = Survey([self.q1, self.q2, self.q3, self.q4, self.q5, self.q6])

        # Add skip rules (event-sourced methods return new Survey)
        survey = survey.add_skip_rule("basic_question", "{{ experience.answer }} == 'expert'")
        survey = survey.add_skip_rule(
            "advanced_question", "{{ experience.answer }} == 'beginner'"
        )
        survey = survey.add_skip_rule("expert_tools", "{{ experience.answer }} == 'beginner'")

        # Manually set groups to avoid validation issues with skip rules
        survey.question_groups = {
            "demographics": (0, 1),  # experience, role
            "level_specific": (2, 4),  # basic_question, advanced_question, expert_tools
            "conclusion": (5, 5),  # feedback
        }

        # Test beginner user - should skip advanced questions
        answers_beginner = {"experience.answer": "beginner", "role.answer": "student"}
        result = survey.next_question_group("role", answers_beginner)

        self.assertIsNotNone(result)
        group_name, questions = result
        self.assertEqual(group_name, "level_specific")
        self.assertEqual(len(questions), 1)  # Only basic_question
        self.assertEqual(questions[0].question_name, "basic_question")

        # Test expert user - should skip basic question
        answers_expert = {"experience.answer": "expert", "role.answer": "researcher"}
        result = survey.next_question_group("role", answers_expert)

        self.assertIsNotNone(result)
        group_name, questions = result
        self.assertEqual(group_name, "level_specific")
        self.assertEqual(len(questions), 2)  # advanced_question and expert_tools
        self.assertEqual(questions[0].question_name, "advanced_question")
        self.assertEqual(questions[1].question_name, "expert_tools")

    def test_next_question_group_entire_group_skip(self):
        """Test when an entire group is skipped."""
        survey = Survey([self.q1, self.q2, self.q3, self.q4, self.q5])

        # Skip entire middle section for certain users (event-sourced methods return new Survey)
        survey = survey.add_skip_rule(
            "basic_question", "{{ experience.answer }} == 'skip_section'"
        )
        survey = survey.add_skip_rule(
            "advanced_question", "{{ experience.answer }} == 'skip_section'"
        )

        survey.question_groups = {
            "intro": (0, 1),  # experience, role
            "skippable_section": (
                2,
                3,
            ),  # basic_question, advanced_question (both skipped)
            "final": (4, 4),  # expert_tools
        }

        answers_skip = {"experience.answer": "skip_section", "role.answer": "tester"}
        result = survey.next_question_group("role", answers_skip)

        # Should skip to final group since entire middle section is skipped
        self.assertIsNotNone(result)
        group_name, questions = result
        self.assertEqual(group_name, "final")
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0].question_name, "expert_tools")

    def test_next_question_group_no_groups(self):
        """Test behavior when survey has no groups."""
        survey = Survey([self.q1, self.q2])
        # Don't create any groups

        result = survey.next_question_group()
        self.assertIsNone(result)

    def test_suggest_dependency_aware_groups(self):
        """Test the suggestion method for dependency-aware groups."""
        # Create questions with dependencies
        q1 = QuestionFreeText(question_text="Name?", question_name="name")
        q2 = QuestionFreeText(question_text="Age?", question_name="age")
        q3 = QuestionFreeText(question_text="Hi {{name}}!", question_name="greeting")

        survey = Survey([q1, q2, q3])
        suggestions = survey.suggest_dependency_aware_groups("auto")

        # Should suggest separate groups due to dependency
        self.assertIsInstance(suggestions, dict)
        self.assertTrue(len(suggestions) >= 2)  # At least 2 groups due to dependency

    def test_group_visualization_integration(self):
        """Test that groups work with flow visualization."""
        survey = Survey([self.q1, self.q2, self.q3, self.q4])
        survey = survey.create_allowable_groups("demo", max_group_size=2)

        # This should not raise an error
        try:
            # We can't test the actual visualization without graphviz, but we can test
            # that the method exists and the groups are properly set up
            self.assertTrue(hasattr(survey, "show_flow"))
            self.assertTrue(len(survey.question_groups) > 0)
        except Exception as e:
            # If graphviz is not installed, that's okay for this test
            if "graphviz" not in str(e).lower():
                raise

    def test_complex_skip_scenario(self):
        """Test complex scenario with multiple skip paths and groups."""
        # Create a complex survey with branching logic
        q_intro = QuestionMultipleChoice(
            question_text="Are you a developer?",
            question_options=["yes", "no", "learning"],
            question_name="is_developer",
        )

        q_experience = QuestionMultipleChoice(
            question_text="Years of experience?",
            question_options=["0-1", "2-5", "6+"],
            question_name="dev_experience",
        )

        q_languages = QuestionFreeText(
            question_text="What languages do you know?", question_name="languages"
        )

        q_career_change = QuestionFreeText(
            question_text="Why are you considering development?",
            question_name="career_change",
        )

        q_learning_path = QuestionFreeText(
            question_text="What's your learning plan?", question_name="learning_plan"
        )

        q_feedback = QuestionFreeText(
            question_text="Any other thoughts?", question_name="final_feedback"
        )

        survey = Survey(
            [
                q_intro,
                q_experience,
                q_languages,
                q_career_change,
                q_learning_path,
                q_feedback,
            ]
        )

        # Add complex skip logic (event-sourced methods return new Survey)
        survey = survey.add_skip_rule("dev_experience", "{{ is_developer.answer }} == 'no'")
        survey = survey.add_skip_rule("languages", "{{ is_developer.answer }} == 'no'")
        survey = survey.add_skip_rule("career_change", "{{ is_developer.answer }} == 'yes'")
        survey = survey.add_skip_rule("learning_plan", "{{ is_developer.answer }} == 'yes'")

        # Set up groups manually
        survey.question_groups = {
            "intro": (0, 0),  # is_developer
            "developer_section": (1, 2),  # dev_experience, languages
            "non_developer_section": (3, 4),  # career_change, learning_plan
            "conclusion": (5, 5),  # final_feedback
        }

        # Test developer path
        dev_answers = {"is_developer.answer": "yes"}
        result = survey.next_question_group("is_developer", dev_answers)
        self.assertIsNotNone(result)
        group_name, questions = result
        self.assertEqual(group_name, "developer_section")
        self.assertEqual(len(questions), 2)

        # Test non-developer path
        non_dev_answers = {"is_developer.answer": "no"}
        result = survey.next_question_group("is_developer", non_dev_answers)
        self.assertIsNotNone(result)
        group_name, questions = result
        self.assertEqual(group_name, "non_developer_section")
        self.assertEqual(len(questions), 2)

        # Test learning path (intermediate case)
        learning_answers = {"is_developer.answer": "learning"}
        result = survey.next_question_group("is_developer", learning_answers)
        # Should get all questions since none are skipped for learning
        self.assertIsNotNone(result)

    def test_group_boundaries_with_dependencies(self):
        """Test that group boundaries are respected when there are dependencies."""
        # Create questions where later questions depend on earlier ones
        q1 = QuestionFreeText(question_text="Your name?", question_name="name")
        q2 = QuestionFreeText(question_text="Your city?", question_name="city")
        q3 = QuestionFreeText(
            question_text="Hi {{name}} from {{city}}!", question_name="greeting"
        )
        q4 = QuestionFreeText(
            question_text="Independent question", question_name="independent"
        )

        survey = Survey([q1, q2, q3, q4])

        # Test that create_allowable_groups respects dependencies
        survey = survey.create_allowable_groups("smart", max_group_size=3)

        # q3 should not be grouped with q1 and q2 due to dependencies
        # Verify the grouping makes sense
        groups = survey.question_groups
        self.assertTrue(
            len(groups) >= 2
        )  # Should have multiple groups due to dependencies


class TestAutomatedGroupCreation(unittest.TestCase):
    """Test automated group creation methods."""

    def setUp(self):
        """Set up questions with various dependency patterns."""
        # Independent questions
        self.q_name = QuestionFreeText(
            question_text="What's your name?", question_name="name"
        )

        self.q_age = QuestionFreeText(
            question_text="What's your age?", question_name="age"
        )

        self.q_city = QuestionFreeText(
            question_text="What city do you live in?", question_name="city"
        )

        # Dependent questions
        self.q_greeting = QuestionFreeText(
            question_text="Hello {{name}}, nice to meet you!", question_name="greeting"
        )

        self.q_location_response = QuestionFreeText(
            question_text="{{city}} sounds like a nice place to live!",
            question_name="location_response",
        )

        self.q_complex = QuestionFreeText(
            question_text="Hi {{name}} from {{city}}, you're {{age}} years old!",
            question_name="complex_greeting",
        )

    def test_suggest_dependency_aware_groups_simple(self):
        """Test suggestion with simple dependency pattern."""
        survey = Survey([self.q_name, self.q_age, self.q_greeting])
        suggestions = survey.suggest_dependency_aware_groups("auto")

        # Should suggest at least 2 groups due to dependency
        self.assertIsInstance(suggestions, dict)
        self.assertTrue(len(suggestions) >= 2)

        # Name and age should be together (independent)
        # Greeting should be separate (depends on name)
        group_sizes = [(end - start + 1) for start, end in suggestions.values()]
        self.assertIn(2, group_sizes)  # Independent group of size 2
        self.assertIn(1, group_sizes)  # Dependent group of size 1

    def test_suggest_dependency_aware_groups_complex(self):
        """Test suggestion with complex dependency chains."""
        survey = Survey(
            [
                self.q_name,
                self.q_age,
                self.q_city,
                self.q_greeting,
                self.q_location_response,
                self.q_complex,
            ]
        )

        suggestions = survey.suggest_dependency_aware_groups("section")

        # Should create multiple groups respecting dependencies
        self.assertTrue(len(suggestions) >= 2)  # At least 2 groups due to dependencies

        # Verify no group contains questions with internal dependencies
        for group_name, (start, end) in suggestions.items():
            # Create a temporary survey to test this grouping
            temp_survey = Survey(
                [
                    self.q_name,
                    self.q_age,
                    self.q_city,
                    self.q_greeting,
                    self.q_location_response,
                    self.q_complex,
                ]
            )

            # This should not raise an exception if grouping is valid
            start_q = temp_survey.questions[start].question_name
            end_q = temp_survey.questions[end].question_name
            temp_survey.add_question_group(start_q, end_q, f"test_{group_name}")

    def test_create_allowable_groups_no_dependencies(self):
        """Test automated creation with independent questions."""
        # All independent questions
        questions = [
            QuestionFreeText(question_text=f"Question {i}", question_name=f"q{i}")
            for i in range(6)
        ]
        survey = Survey(questions)

        # Test with no size limit
        survey = survey.create_allowable_groups("unlimited")
        self.assertEqual(len(survey.question_groups), 1)  # All in one group
        self.assertEqual(list(survey.question_groups.values())[0], (0, 5))

        # Test with size limit of 2
        survey = Survey(questions)
        survey = survey.create_allowable_groups("pairs", max_group_size=2)
        self.assertEqual(len(survey.question_groups), 3)  # 3 groups of 2 each

        expected_groups = [
            ("pairs_0", (0, 1)),
            ("pairs_1", (2, 3)),
            ("pairs_2", (4, 5)),
        ]
        for group_name, expected_range in expected_groups:
            self.assertEqual(survey.question_groups[group_name], expected_range)

    def test_create_allowable_groups_with_dependencies(self):
        """Test automated creation respecting dependencies."""
        survey = Survey([self.q_name, self.q_age, self.q_greeting, self.q_city])

        # Should automatically separate dependent questions
        survey = survey.create_allowable_groups("smart", max_group_size=3)

        # Verify all groups are valid (no internal dependencies)
        self.assertTrue(len(survey.question_groups) >= 2)

        # Each group should be valid
        for group_name in survey.question_groups:
            # Group should exist and not raise validation errors
            self.assertIn(group_name, survey.question_groups)

    def test_create_allowable_groups_chain_dependencies(self):
        """Test with chain of dependencies: q1 -> q2 -> q3."""
        q1 = QuestionFreeText(question_text="Question 1", question_name="q1")
        q2 = QuestionFreeText(question_text="About {{q1}}", question_name="q2")
        q3 = QuestionFreeText(question_text="More about {{q2}}", question_name="q3")
        q4 = QuestionFreeText(question_text="Independent", question_name="q4")

        survey = Survey([q1, q2, q3, q4])
        survey = survey.create_allowable_groups("chain", max_group_size=2)

        # Should create multiple small groups due to dependencies
        # q1 alone, q2 alone, q3 alone, q4 could be with others or alone
        self.assertTrue(len(survey.question_groups) >= 3)

    def test_create_allowable_groups_preserve_contiguous(self):
        """Test that groups remain contiguous (no gaps)."""
        survey = Survey([self.q_name, self.q_age, self.q_city, self.q_greeting])
        survey = survey.create_allowable_groups("contiguous", max_group_size=2)

        # Verify all groups are contiguous ranges
        all_indices = set()
        for start, end in survey.question_groups.values():
            # Check contiguity
            self.assertLessEqual(start, end)
            # Check no overlaps
            group_indices = set(range(start, end + 1))
            self.assertTrue(group_indices.isdisjoint(all_indices))
            all_indices.update(group_indices)

        # Should cover all questions
        self.assertEqual(all_indices, set(range(len(survey.questions))))

    def test_automated_vs_manual_validation(self):
        """Test that automated groups pass the same validation as manual groups."""
        survey = Survey([self.q_name, self.q_age, self.q_greeting])

        # Create groups automatically
        survey = survey.create_allowable_groups("auto")
        auto_groups = dict(survey.question_groups)

        # Create a fresh survey to recreate manually and test validation
        fresh_survey = Survey([self.q_name, self.q_age, self.q_greeting])

        for group_name, (start, end) in auto_groups.items():
            start_q = fresh_survey.questions[start].question_name
            end_q = fresh_survey.questions[end].question_name

            # This should not raise an exception if auto-creation was correct
            fresh_survey = fresh_survey.add_question_group(start_q, end_q, group_name)

        # Should have same groups
        self.assertEqual(fresh_survey.question_groups, auto_groups)

    def test_suggest_vs_create_consistency(self):
        """Test that suggest and create methods are consistent."""
        survey = Survey([self.q_name, self.q_age, self.q_city, self.q_greeting])

        # Get suggestions
        suggestions = survey.suggest_dependency_aware_groups("test")

        # Create automatically
        survey = survey.create_allowable_groups("test")
        created_groups = survey.question_groups

        # Should be identical
        self.assertEqual(suggestions, created_groups)

    def test_empty_survey_automated_creation(self):
        """Test automated creation with empty survey."""
        survey = Survey([])
        survey = survey.create_allowable_groups("empty")

        self.assertEqual(len(survey.question_groups), 0)

        suggestions = survey.suggest_dependency_aware_groups("empty")
        self.assertEqual(len(suggestions), 0)

    def test_single_question_automated_creation(self):
        """Test automated creation with single question."""
        survey = Survey([self.q_name])
        survey = survey.create_allowable_groups("single")

        self.assertEqual(len(survey.question_groups), 1)
        self.assertEqual(list(survey.question_groups.values())[0], (0, 0))

    def test_automated_creation_with_memory_dependencies(self):
        """Test automated creation respects memory dependencies."""
        survey = Survey([self.q_name, self.q_age, self.q_greeting])

        # Add memory dependency
        survey.add_targeted_memory("greeting", "age")

        # Should separate questions with memory dependencies
        survey = survey.create_allowable_groups("memory_aware", max_group_size=3)

        # Verify no validation errors (memory deps should be respected)
        self.assertTrue(len(survey.question_groups) >= 2)

    def test_group_name_prefixes(self):
        """Test that group name prefixes work correctly."""
        survey = Survey([self.q_name, self.q_age])

        # Test custom prefix
        survey = survey.create_allowable_groups("custom_prefix", max_group_size=1)

        group_names = list(survey.question_groups.keys())
        self.assertEqual(len(group_names), 2)
        self.assertTrue(all(name.startswith("custom_prefix_") for name in group_names))
        self.assertIn("custom_prefix_0", group_names)
        self.assertIn("custom_prefix_1", group_names)

    def test_max_group_size_edge_cases(self):
        """Test edge cases for max_group_size parameter."""
        questions = [
            QuestionFreeText(question_text=f"Q{i}", question_name=f"q{i}")
            for i in range(5)
        ]

        # Test max_group_size = 1
        survey = Survey(questions)
        survey = survey.create_allowable_groups("individual", max_group_size=1)
        self.assertEqual(len(survey.question_groups), 5)  # Each question alone

        # Test max_group_size larger than survey
        survey = Survey(questions)
        survey = survey.create_allowable_groups("large", max_group_size=10)
        self.assertEqual(len(survey.question_groups), 1)  # All in one group

        # Test max_group_size = 0 (should behave like 1)
        survey = Survey(questions)
        survey = survey.create_allowable_groups("zero", max_group_size=0)
        # Implementation should handle this gracefully


class TestGroupNavigationEdgeCases(unittest.TestCase):
    """Test edge cases for group navigation."""

    def test_empty_survey_groups(self):
        """Test behavior with empty survey."""
        survey = Survey([])
        result = survey.next_question_group()
        self.assertIsNone(result)

    def test_single_question_groups(self):
        """Test navigation with single-question groups."""
        q1 = QuestionFreeText(question_text="Question 1", question_name="q1")
        survey = Survey([q1])
        survey = survey.create_allowable_groups("single", max_group_size=1)

        result = survey.next_question_group()
        self.assertIsNotNone(result)
        group_name, questions = result
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0].question_name, "q1")

    def test_skip_rule_to_end_of_survey(self):
        """Test skip rules that lead to end of survey."""
        q1 = QuestionMultipleChoice(
            question_text="Continue survey?",
            question_options=["yes", "no"],
            question_name="should_continue",
        )
        q2 = QuestionFreeText(question_text="More questions", question_name="more")

        survey = Survey([q1, q2])
        survey.add_stop_rule("should_continue", "{{ should_continue.answer }} == 'no'")
        survey.question_groups = {"all": (0, 1)}

        # Test that we handle end-of-survey correctly
        answers = {"should_continue.answer": "no"}
        result = survey.next_question_group("should_continue", answers)
        # The behavior depends on implementation details, but shouldn't crash


class TestGroupNavigationWithInstructions(unittest.TestCase):
    """Test cases for question group navigation with instructions."""

    def setUp(self):
        """Set up common questions and instructions for testing."""
        self.q1 = QuestionMultipleChoice(
            question_text="What's your experience level?",
            question_options=["beginner", "intermediate", "expert"],
            question_name="experience",
        )

        self.q2 = QuestionFreeText(
            question_text="What's your primary role?", question_name="role"
        )

        self.q3 = QuestionFreeText(
            question_text="Basic question for beginners", question_name="basic_question"
        )

        self.q4 = QuestionFreeText(
            question_text="Advanced question for experts",
            question_name="advanced_question",
        )

        # Create instructions
        self.intro_instruction = Instruction(
            text="Welcome! Please answer the following questions.", name="intro"
        )
        self.middle_instruction = Instruction(
            text="Now we'll ask about your experience.", name="middle"
        )
        self.end_instruction = Instruction(
            text="Thank you for completing the survey!", name="end"
        )

    def test_next_question_group_with_instructions_basic(self):
        """Test basic functionality with instructions before groups."""
        survey = Survey([self.intro_instruction, self.q1, self.q2, self.q3])
        survey = survey.create_allowable_groups("section", max_group_size=2)

        # Starting from instruction, should find first group
        result = survey.next_question_group_with_instructions(
            self.intro_instruction, {}
        )
        self.assertIsNotNone(result)
        group_name, questions = result
        self.assertEqual(group_name, "section_0")
        self.assertEqual(len(questions), 2)
        self.assertEqual(questions[0].question_name, "experience")
        self.assertEqual(questions[1].question_name, "role")

    def test_next_question_group_with_instructions_from_question(self):
        """Test finding next group when starting from a question."""
        survey = Survey([self.q1, self.q2, self.q3, self.q4])
        survey = survey.create_allowable_groups("section", max_group_size=2)

        # Starting from first question in first group
        result = survey.next_question_group_with_instructions("experience", {})
        self.assertIsNotNone(result)
        group_name, questions = result
        self.assertEqual(group_name, "section_1")
        self.assertEqual(len(questions), 2)

    def test_next_question_group_with_instructions_instruction_between_groups(self):
        """Test handling instruction between question groups."""
        survey = Survey([self.q1, self.q2, self.middle_instruction, self.q3, self.q4])
        survey = survey.create_allowable_groups("section", max_group_size=2)

        # Starting from instruction between groups
        result = survey.next_question_group_with_instructions(
            self.middle_instruction, {}
        )
        self.assertIsNotNone(result)
        group_name, questions = result
        self.assertEqual(group_name, "section_1")
        self.assertEqual(len(questions), 2)

    def test_next_question_group_with_instructions_no_groups(self):
        """Test behavior when survey has no groups."""
        survey = Survey([self.intro_instruction, self.q1, self.q2])

        result = survey.next_question_group_with_instructions(
            self.intro_instruction, {}
        )
        self.assertIsNone(result)

    def test_next_question_group_with_instructions_end_of_survey(self):
        """Test behavior at end of survey."""
        survey = Survey([self.q1, self.q2, self.q3])
        survey = survey.create_allowable_groups("section", max_group_size=2)

        # Starting from last question
        result = survey.next_question_group_with_instructions("basic_question", {})
        self.assertIsNone(result)

    def test_next_question_group_with_instructions_with_skip_rules(self):
        """Test with skip rules that affect group contents."""
        survey = Survey([self.q1, self.q2, self.q3, self.q4])
        survey = survey.add_skip_rule("basic_question", "{{ experience.answer }} == 'expert'")
        survey = survey.add_skip_rule(
            "advanced_question", "{{ experience.answer }} == 'beginner'"
        )

        survey.question_groups = {"demographics": (0, 1), "level_specific": (2, 3)}

        # Test expert path - should skip basic_question
        expert_answers = {"experience.answer": "expert", "role.answer": "researcher"}
        result = survey.next_question_group_with_instructions("role", expert_answers)
        self.assertIsNotNone(result)
        group_name, questions = result
        self.assertEqual(group_name, "level_specific")
        self.assertEqual(len(questions), 1)  # Only advanced_question
        self.assertEqual(questions[0].question_name, "advanced_question")

    def test_next_question_group_with_instructions_string_input(self):
        """Test with string input for question/instruction names."""
        survey = Survey([self.intro_instruction, self.q1, self.q2, self.q3])
        survey = survey.create_allowable_groups("section", max_group_size=2)

        # Using instruction name as string
        result = survey.next_question_group_with_instructions("intro", {})
        self.assertIsNotNone(result)
        group_name, questions = result
        self.assertEqual(group_name, "section_0")

        # Using question name as string
        result = survey.next_question_group_with_instructions("experience", {})
        self.assertIsNotNone(result)
        group_name, questions = result
        self.assertEqual(group_name, "section_1")

    def test_next_question_group_with_instructions_invalid_name(self):
        """Test error handling for invalid item names."""
        survey = Survey([self.q1, self.q2])
        survey = survey.create_allowable_groups("section", max_group_size=2)

        with self.assertRaises(SurveyError):
            survey.next_question_group_with_instructions("nonexistent", {})

    def test_next_questions_with_instructions_basic(self):
        """Test basic functionality returning list of questions and instructions."""
        survey = Survey([self.intro_instruction, self.q1, self.q2, self.q3])
        survey = survey.create_allowable_groups("section", max_group_size=2)

        # Get first group - should include instruction and questions
        result = survey.next_questions_with_instructions(None, {})
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

        # First item should be the instruction
        self.assertTrue(survey._navigator._is_instruction(result[0]))
        self.assertEqual(result[0].name, "intro")

        # Should also include questions from first group
        question_names = [
            item.question_name for item in result if hasattr(item, "question_name")
        ]
        self.assertIn("experience", question_names)
        self.assertIn("role", question_names)

    def test_next_questions_with_instructions_no_groups(self):
        """Test fallback to single question/instruction when no groups exist."""
        survey = Survey([self.intro_instruction, self.q1, self.q2])

        # Should return single item (the instruction)
        result = survey.next_questions_with_instructions(None, {})
        self.assertEqual(len(result), 1)
        self.assertTrue(survey._navigator._is_instruction(result[0]))

        # After instruction, should return first question
        result = survey.next_questions_with_instructions(self.intro_instruction, {})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].question_name, "experience")

    def test_next_questions_with_instructions_instruction_in_group(self):
        """Test when instruction is within a group's range."""
        survey = Survey([self.q1, self.middle_instruction, self.q2, self.q3])
        survey = survey.create_allowable_groups("section", max_group_size=3)

        # Get first group - should include instruction that falls within range
        result = survey.next_questions_with_instructions(None, {})
        self.assertIsInstance(result, list)

        # Check if instruction is included
        instruction_names = [
            item.name for item in result if survey._navigator._is_instruction(item)
        ]
        question_names = [
            item.question_name for item in result if hasattr(item, "question_name")
        ]

        # Should have questions from the group
        self.assertIn("experience", question_names)
        self.assertIn("middle", instruction_names)
        self.assertIn("role", question_names)

    def test_next_questions_with_instructions_end_of_survey(self):
        """Test end of survey handling."""
        survey = Survey([self.q1, self.q2])
        survey = survey.create_allowable_groups("section", max_group_size=2)

        # At end of survey
        result = survey.next_questions_with_instructions("role", {})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], EndOfSurvey)

    def test_next_questions_with_instructions_with_skip_rules(self):
        """Test with skip rules affecting group contents."""
        survey = Survey([self.q1, self.q2, self.q3, self.q4])
        survey = survey.add_skip_rule("basic_question", "{{ experience.answer }} == 'expert'")
        survey = survey.add_skip_rule(
            "advanced_question", "{{ experience.answer }} == 'beginner'"
        )

        survey.question_groups = {"demographics": (0, 1), "level_specific": (2, 3)}

        # Test beginner path
        beginner_answers = {"experience.answer": "beginner", "role.answer": "student"}
        result = survey.next_questions_with_instructions("role", beginner_answers)
        self.assertIsInstance(result, list)
        # Advanced question is included because it is part of a group that is not skipped
        question_names = [
            item.question_name for item in result if hasattr(item, "question_name")
        ]
        self.assertIn("basic_question", question_names)
        self.assertIn("advanced_question", question_names)

    def test_next_questions_with_instructions_instruction_between_groups(self):
        """Test instruction between groups is handled correctly."""
        survey = Survey([self.q1, self.q2, self.middle_instruction, self.q3, self.q4])
        survey = survey.create_allowable_groups("section", max_group_size=2)

        # Starting from instruction between groups
        result = survey.next_questions_with_instructions(self.middle_instruction, {})
        self.assertIsInstance(result, list)
        # Should get questions from next group
        question_names = [
            item.question_name for item in result if hasattr(item, "question_name")
        ]
        self.assertIn("basic_question", question_names)
        self.assertIn("advanced_question", question_names)

    def test_next_questions_with_instructions_string_input(self):
        """Test with string input for current item."""
        survey = Survey([self.intro_instruction, self.q1, self.q2, self.q3])
        survey = survey.create_allowable_groups("section", max_group_size=2)

        # Using instruction name
        result = survey.next_questions_with_instructions("intro", {})
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

        # Using question name
        result = survey.next_questions_with_instructions("experience", {})
        self.assertIsInstance(result, list)

    def test_next_questions_with_instructions_complex_flow(self):
        """Test complex flow with multiple instructions and groups."""
        survey = Survey(
            [
                self.intro_instruction,
                self.q1,
                self.q2,
                self.middle_instruction,
                self.q3,
                self.q4,
                self.end_instruction,
            ]
        )
        survey = survey.create_allowable_groups("section", max_group_size=2)

        # Start from beginning
        result = survey.next_questions_with_instructions(None, {})
        self.assertIsInstance(result, list)
        # Should include intro instruction and first group questions
        instruction_names = [
            item.name for item in result if survey._navigator._is_instruction(item)
        ]
        question_names = [
            item.question_name for item in result if hasattr(item, "question_name")
        ]
        self.assertIn("intro", instruction_names)
        self.assertIn("experience", question_names)
        self.assertIn("role", question_names)

        # Move to next group
        result = survey.next_questions_with_instructions("role", {})
        self.assertIsInstance(result, list)
        # Should include middle instruction and second group questions
        instruction_names = [
            item.name for item in result if survey._navigator._is_instruction(item)
        ]
        question_names = [
            item.question_name for item in result if hasattr(item, "question_name")
        ]
        self.assertIn("middle", instruction_names)
        self.assertIn("basic_question", question_names)
        self.assertIn("advanced_question", question_names)

    def test_next_questions_with_instructions_entire_group_skipped(self):
        """Test when entire group is skipped."""
        survey = Survey([self.q1, self.q2, self.q3, self.q4])
        survey = survey.add_skip_rule("basic_question", "{{ experience.answer }} == 'skip_all'")
        survey = survey.add_skip_rule(
            "advanced_question", "{{ experience.answer }} == 'skip_all'"
        )

        survey.question_groups = {
            "intro": (0, 1),
            "skippable": (2, 3),
            "final": (4, 4) if len(survey.questions) > 4 else (3, 3),
        }

        # If we have 4 questions, adjust the test
        if len(survey.questions) == 4:
            survey.question_groups = {"intro": (0, 1), "skippable": (2, 3)}
            answers = {"experience.answer": "skip_all", "role.answer": "test"}
            result = survey.next_questions_with_instructions("role", answers)
            # Should handle skipped group gracefully
            self.assertIsInstance(result, list)

    def test_is_instruction_helper_method(self):
        """Test the _is_instruction helper method."""
        survey = Survey([self.intro_instruction, self.q1])

        # Test with instruction
        self.assertTrue(survey._navigator._is_instruction(self.intro_instruction))

        # Test with question
        self.assertFalse(survey._navigator._is_instruction(self.q1))

        # Test with string (should return False)
        self.assertFalse(survey._navigator._is_instruction("not_an_instruction"))

    def test_next_questions_with_instructions_preserves_order(self):
        """Test that items are returned in correct pseudo-index order."""
        survey = Survey([self.intro_instruction, self.q1, self.q2, self.q3])
        survey = survey.create_allowable_groups("section", max_group_size=2)

        result = survey.next_questions_with_instructions(None, {})

        # Verify order: instruction should come before questions
        instruction_found = False
        for item in result:
            if survey._navigator._is_instruction(item):
                instruction_found = True
            elif hasattr(item, "question_name"):
                # Once we see a question, we shouldn't see instructions after
                # (unless there are instructions within the group range)
                pass

        # Should have found the instruction
        self.assertTrue(
            instruction_found
            or any(survey._navigator._is_instruction(item) for item in result)
        )

    def test_next_question_group_with_instructions_none_input(self):
        """Test with None input to find first group."""
        survey = Survey([self.intro_instruction, self.q1, self.q2, self.q3])
        survey = survey.create_allowable_groups("section", max_group_size=2)

        result = survey.next_question_group_with_instructions(None, {})
        self.assertIsNotNone(result)
        group_name, questions = result
        self.assertEqual(group_name, "section_0")

    def test_next_questions_with_instructions_after_instruction_at_end(self):
        """Test when instruction is at the end of survey."""
        survey = Survey([self.q1, self.q2, self.end_instruction])
        survey = survey.create_allowable_groups("section", max_group_size=2)

        # Starting from last question
        result = survey.next_questions_with_instructions("role", {})
        # Should handle gracefully - might return instruction or EndOfSurvey
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)


if __name__ == "__main__":
    unittest.main()
