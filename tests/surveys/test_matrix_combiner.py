"""
Tests for matrix combiner functionality in surveys.

This module tests the combine_multiple_choice_to_matrix method and related functionality
for combining multiple choice questions into matrix questions.
"""

import pytest
from edsl import Survey, QuestionMultipleChoice, QuestionFreeText
from edsl.questions import QuestionMatrix
from edsl.surveys.survey_helpers.matrix_combiner import combine_multiple_choice_to_matrix, _find_common_prefix_and_items


class TestMatrixCombiner:
    """Test cases for matrix combination functionality."""

    def setup_method(self):
        """Set up test data for each test method."""
        # Basic satisfaction questions with same options
        self.q_work = QuestionMultipleChoice(
            question_name="satisfaction_work",
            question_text="How satisfied are you with your work?",
            question_options=["Very satisfied", "Somewhat satisfied", "Not satisfied"]
        )

        self.q_pay = QuestionMultipleChoice(
            question_name="satisfaction_pay",
            question_text="How satisfied are you with your pay?",
            question_options=["Very satisfied", "Somewhat satisfied", "Not satisfied"]
        )

        self.q_benefits = QuestionMultipleChoice(
            question_name="satisfaction_benefits",
            question_text="How satisfied are you with your benefits?",
            question_options=["Very satisfied", "Somewhat satisfied", "Not satisfied"]
        )

        # Questions for inference testing (user examples)
        self.q_trust_no_ai = QuestionMultipleChoice(
            question_name="trust_no_ai",
            question_text="Overall, how much would you trust the work delivered by: - A freelancer who completed their work without using AI tools",
            question_options=["High trust", "Medium trust", "Low trust"]
        )

        self.q_trust_with_ai = QuestionMultipleChoice(
            question_name="trust_with_ai",
            question_text="Overall, how much would you trust the work delivered by: - A freelancer who used AI tools to assist them with their work",
            question_options=["High trust", "Medium trust", "Low trust"]
        )

        # Questions with different options (for error testing)
        self.q_different_options = QuestionMultipleChoice(
            question_name="different",
            question_text="Different question",
            question_options=["A", "B", "C"]
        )

        # Non-multiple choice question (for error testing)
        self.q_free_text = QuestionFreeText(
            question_name="free_text",
            question_text="What is your opinion?"
        )

    def test_basic_combination_with_explicit_text(self):
        """Test basic matrix combination with explicitly provided matrix question text."""
        survey = Survey().add_question(self.q_work).add_question(self.q_pay)

        result = survey.combine_multiple_choice_to_matrix(
            question_names=["satisfaction_work", "satisfaction_pay"],
            matrix_question_name="satisfaction_matrix",
            matrix_question_text="How satisfied are you with each aspect?"
        )

        # Check result structure
        assert len(result.questions) == 1
        matrix_q = result.questions[0]
        assert isinstance(matrix_q, QuestionMatrix)
        assert matrix_q.question_name == "satisfaction_matrix"
        assert matrix_q.question_text == "How satisfied are you with each aspect?"
        assert matrix_q.question_items == [
            "How satisfied are you with your work?",
            "How satisfied are you with your pay?"
        ]
        assert matrix_q.question_options == ["Very satisfied", "Somewhat satisfied", "Not satisfied"]

    def test_combination_with_inference(self):
        """Test matrix combination with automatic text and item inference."""
        survey = Survey().add_question(self.q_trust_no_ai).add_question(self.q_trust_with_ai)

        result = survey.combine_multiple_choice_to_matrix(
            question_names=["trust_no_ai", "trust_with_ai"],
            matrix_question_name="trust_matrix"
            # No matrix_question_text provided - should be inferred
        )

        matrix_q = result.questions[0]
        assert matrix_q.question_text == "Overall, how much would you trust the work delivered by"
        assert matrix_q.question_items == [
            "A freelancer who completed their work without using AI tools",
            "A freelancer who used AI tools to assist them with their work"
        ]

    def test_keep_original_questions(self):
        """Test matrix combination while keeping original questions."""
        survey = Survey().add_question(self.q_work).add_question(self.q_pay).add_question(self.q_benefits)

        result = survey.combine_multiple_choice_to_matrix(
            question_names=["satisfaction_work", "satisfaction_pay"],
            matrix_question_name="satisfaction_matrix",
            matrix_question_text="How satisfied are you with work aspects?",
            remove_original_questions=False
        )

        # Should have 4 questions: 3 original + 1 matrix
        assert len(result.questions) == 4
        question_names = result.question_names
        assert "satisfaction_work" in question_names
        assert "satisfaction_pay" in question_names
        assert "satisfaction_benefits" in question_names
        assert "satisfaction_matrix" in question_names

    def test_use_question_names_as_items(self):
        """Test using question names instead of question text as matrix items."""
        survey = Survey().add_question(self.q_work).add_question(self.q_pay)

        result = survey.combine_multiple_choice_to_matrix(
            question_names=["satisfaction_work", "satisfaction_pay"],
            matrix_question_name="satisfaction_matrix",
            matrix_question_text="Rate these areas",
            use_question_text_as_items=False
        )

        matrix_q = result.questions[0]
        assert matrix_q.question_items == ["satisfaction_work", "satisfaction_pay"]

    def test_survey_immutability(self):
        """Test that the original survey is not modified."""
        survey = Survey().add_question(self.q_work).add_question(self.q_pay).add_question(self.q_benefits)
        original_question_count = len(survey.questions)
        original_question_names = survey.question_names.copy()

        # Apply matrix combination
        result = survey.combine_multiple_choice_to_matrix(
            question_names=["satisfaction_work", "satisfaction_pay"],
            matrix_question_name="satisfaction_matrix",
            matrix_question_text="Test"
        )

        # Original survey should be unchanged
        assert len(survey.questions) == original_question_count
        assert survey.question_names == original_question_names

        # Result should be different
        assert len(result.questions) != original_question_count
        assert result.question_names != original_question_names

    def test_error_nonexistent_questions(self):
        """Test error when trying to combine non-existent questions."""
        survey = Survey().add_question(self.q_work)

        with pytest.raises(ValueError, match="Questions not found in survey"):
            survey.combine_multiple_choice_to_matrix(
                question_names=["satisfaction_work", "nonexistent"],
                matrix_question_name="test_matrix",
                matrix_question_text="Test"
            )

    def test_error_non_multiple_choice_questions(self):
        """Test error when trying to combine non-multiple choice questions."""
        survey = Survey().add_question(self.q_work).add_question(self.q_free_text)

        with pytest.raises(ValueError, match="is not a multiple choice question"):
            survey.combine_multiple_choice_to_matrix(
                question_names=["satisfaction_work", "free_text"],
                matrix_question_name="test_matrix",
                matrix_question_text="Test"
            )

    def test_error_incompatible_options(self):
        """Test error when questions have different options."""
        survey = Survey().add_question(self.q_work).add_question(self.q_different_options)

        with pytest.raises(ValueError, match="All questions must have the same options"):
            survey.combine_multiple_choice_to_matrix(
                question_names=["satisfaction_work", "different"],
                matrix_question_name="test_matrix",
                matrix_question_text="Test"
            )

    def test_option_labels_empty_when_not_supported(self):
        """Test that option labels are empty when source questions don't support them."""
        # QuestionMultipleChoice doesn't have option_labels parameter
        q1 = QuestionMultipleChoice(
            question_name="rating1",
            question_text="Rate this item",
            question_options=[1, 2, 3, 4, 5]
        )

        q2 = QuestionMultipleChoice(
            question_name="rating2",
            question_text="Rate this other item",
            question_options=[1, 2, 3, 4, 5]
        )

        survey = Survey().add_question(q1).add_question(q2)

        result = survey.combine_multiple_choice_to_matrix(
            question_names=["rating1", "rating2"],
            matrix_question_name="rating_matrix",
            matrix_question_text="Rate these items"
        )

        matrix_q = result.questions[0]
        # Should have empty option_labels since source questions don't support them
        assert matrix_q.option_labels == {}

    def test_custom_index_placement(self):
        """Test placing matrix question at a specific index."""
        survey = Survey().add_question(self.q_work).add_question(self.q_pay).add_question(self.q_benefits)

        result = survey.combine_multiple_choice_to_matrix(
            question_names=["satisfaction_work", "satisfaction_pay"],
            matrix_question_name="satisfaction_matrix",
            matrix_question_text="Test",
            remove_original_questions=False,
            index=1  # Insert at position 1
        )

        # Matrix should be at position 1
        assert result.question_names[1] == "satisfaction_matrix"


class TestCommonPrefixInference:
    """Test cases for the common prefix inference functionality."""

    def test_user_example_inference(self):
        """Test inference with the exact user examples."""
        question_texts = [
            "Overall, how much would you trust the work delivered by: - A freelancer who completed their work without using AI tools",
            "Overall, how much would you trust the work delivered by: - A freelancer who used AI tools to assist them with their work"
        ]

        prefix, items = _find_common_prefix_and_items(question_texts)

        assert prefix == "Overall, how much would you trust the work delivered by"
        assert items == [
            "A freelancer who completed their work without using AI tools",
            "A freelancer who used AI tools to assist them with their work"
        ]

    def test_colon_separator_inference(self):
        """Test inference with colon separators."""
        question_texts = [
            "How satisfied are you with: Work environment",
            "How satisfied are you with: Compensation package",
            "How satisfied are you with: Career development"
        ]

        prefix, items = _find_common_prefix_and_items(question_texts)

        assert prefix == "How satisfied are you with"
        assert items == ["Work environment", "Compensation package", "Career development"]

    def test_no_clear_pattern_fallback(self):
        """Test fallback behavior when no clear pattern exists."""
        question_texts = [
            "Do you like apples?",
            "Do you prefer oranges?"
        ]

        prefix, items = _find_common_prefix_and_items(question_texts)

        # Should fall back to generic prefix due to short common part
        assert prefix == "Please rate each of the following"
        assert len(items) == 2

    def test_single_question_inference(self):
        """Test inference with a single question."""
        question_texts = [
            "Rate this item: - Quality of service"
        ]

        prefix, items = _find_common_prefix_and_items(question_texts)

        assert prefix == "Rate this item"
        assert items == ["Quality of service"]

    def test_empty_input(self):
        """Test inference with empty input."""
        prefix, items = _find_common_prefix_and_items([])

        assert prefix == ""
        assert items == []


class TestDirectFunctionCall:
    """Test the standalone combine_multiple_choice_to_matrix function."""

    def test_direct_function_call(self):
        """Test calling the function directly instead of through Survey method."""
        q1 = QuestionMultipleChoice(
            question_name="q1",
            question_text="Question 1",
            question_options=["A", "B", "C"]
        )
        q2 = QuestionMultipleChoice(
            question_name="q2",
            question_text="Question 2",
            question_options=["A", "B", "C"]
        )

        survey = Survey().add_question(q1).add_question(q2)

        result = combine_multiple_choice_to_matrix(
            survey=survey,
            question_names=["q1", "q2"],
            matrix_question_name="combined",
            matrix_question_text="Test questions"
        )

        assert len(result.questions) == 1
        assert result.questions[0].question_name == "combined"