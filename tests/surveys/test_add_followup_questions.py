"""Tests for the Survey.add_followup_questions() method"""

import pytest
from edsl import QuestionMultipleChoice, QuestionFreeText, QuestionCheckBox, Survey
from edsl.surveys.base import EndOfSurvey


class TestAddFollowupQuestions:
    """Test the add_followup_questions() method"""

    def test_basic_multiple_choice(self):
        """Test basic usage with multiple choice question"""
        q_rest = QuestionMultipleChoice(
            question_name="restaurants",
            question_text="Which restaurant do you prefer?",
            question_options=["Italian", "Chinese", "Mexican"]
        )

        q_followup = QuestionFreeText(
            question_name="why_restaurant",
            question_text="Why do you like {{ restaurants.answer }}?"
        )

        s = Survey([q_rest]).add_followup_questions("restaurants", q_followup)

        # Should have 4 questions: 1 original + 3 follow-ups
        assert len(s.questions) == 4
        assert s.questions[0].question_name == "restaurants"
        assert s.questions[1].question_name == "why_restaurant_restaurants_0"
        assert s.questions[2].question_name == "why_restaurant_restaurants_1"
        assert s.questions[3].question_name == "why_restaurant_restaurants_2"

        # Check that text substitution happened
        assert s.questions[1].question_text == "Why do you like Italian?"
        assert s.questions[2].question_text == "Why do you like Chinese?"
        assert s.questions[3].question_text == "Why do you like Mexican?"

    def test_with_additional_question_after(self):
        """Test with an additional question after the followups"""
        q_rest = QuestionMultipleChoice(
            question_name="restaurants",
            question_text="Which restaurant?",
            question_options=["Italian", "Chinese"]
        )

        q_followup = QuestionFreeText(
            question_name="why",
            question_text="Why {{ restaurants.answer }}?"
        )

        q_final = QuestionFreeText(
            question_name="overall",
            question_text="Final thoughts?"
        )

        s = Survey([q_rest, q_final]).add_followup_questions("restaurants", q_followup)

        # Should have 4 questions total
        assert len(s.questions) == 4
        assert s.questions[0].question_name == "restaurants"
        assert s.questions[1].question_name == "why_restaurants_0"
        assert s.questions[2].question_name == "why_restaurants_1"
        assert s.questions[3].question_name == "overall"

    def test_checkbox_question(self):
        """Test with checkbox question"""
        q_hobbies = QuestionCheckBox(
            question_name="hobbies",
            question_text="What are your hobbies?",
            question_options=["Reading", "Sports", "Music"]
        )

        q_hobby_followup = QuestionFreeText(
            question_name="hobby_detail",
            question_text="Tell me more about {{ hobbies.answer }}"
        )

        s = Survey([q_hobbies]).add_followup_questions("hobbies", q_hobby_followup)

        assert len(s.questions) == 4
        assert s.questions[1].question_text == "Tell me more about Reading"
        assert s.questions[2].question_text == "Tell me more about Sports"
        assert s.questions[3].question_text == "Tell me more about Music"

    def test_flow_italian(self):
        """Test survey flow when Italian is selected"""
        q_rest = QuestionMultipleChoice(
            question_name="restaurants",
            question_text="Which restaurant?",
            question_options=["Italian", "Chinese"]
        )

        q_followup = QuestionFreeText(
            question_name="why",
            question_text="Why {{ restaurants.answer }}?"
        )

        q_final = QuestionFreeText(
            question_name="overall",
            question_text="Final thoughts?"
        )

        s = Survey([q_rest, q_final]).add_followup_questions("restaurants", q_followup)

        # Simulate answering "Italian"
        answers = {"restaurants.answer": "Italian"}

        # After restaurants, should go to the Italian followup
        next_q = s.next_question("restaurants", answers)
        assert next_q.question_name == "why_restaurants_0"

        # After Italian followup, should go to overall
        answers["why_restaurants_0.answer"] = "Because it's delicious"
        next_q = s.next_question("why_restaurants_0", answers)
        assert next_q.question_name == "overall"

    def test_flow_chinese(self):
        """Test survey flow when Chinese is selected"""
        q_rest = QuestionMultipleChoice(
            question_name="restaurants",
            question_text="Which restaurant?",
            question_options=["Italian", "Chinese"]
        )

        q_followup = QuestionFreeText(
            question_name="why",
            question_text="Why {{ restaurants.answer }}?"
        )

        q_final = QuestionFreeText(
            question_name="overall",
            question_text="Final thoughts?"
        )

        s = Survey([q_rest, q_final]).add_followup_questions("restaurants", q_followup)

        # Simulate answering "Chinese"
        answers = {"restaurants.answer": "Chinese"}

        # After restaurants, should go to the Chinese followup (skipping Italian)
        next_q = s.next_question("restaurants", answers)
        assert next_q.question_name == "why_restaurants_1"

        # After Chinese followup, should go to overall
        answers["why_restaurants_1.answer"] = "Love the flavors"
        next_q = s.next_question("why_restaurants_1", answers)
        assert next_q.question_name == "overall"

    def test_error_on_non_option_question(self):
        """Test that an error is raised when using a question without options"""
        q_text = QuestionFreeText(
            question_name="feedback",
            question_text="Your feedback?"
        )

        q_followup = QuestionFreeText(
            question_name="why",
            question_text="Why?"
        )

        s = Survey([q_text])

        with pytest.raises(ValueError, match="must have options"):
            s.add_followup_questions("feedback", q_followup)
