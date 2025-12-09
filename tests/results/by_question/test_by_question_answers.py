"""Simple tests for ByQuestionAnswers functionality."""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


def test_multiple_choice():
    """Test multiple choice analyzer."""
    from edsl.questions import QuestionMultipleChoice
    from edsl.results.by_question.by_question_answers import ByQuestionAnswers

    q = QuestionMultipleChoice(
        question_name="color",
        question_text="Favorite color?",
        question_options=["Red", "Blue", "Green"],
    )

    answers = ["Red", "Blue", "Red", "Green", "Red"]
    analyzer = ByQuestionAnswers.create(q, answers)

    # Test that we get the right type
    assert analyzer.__class__.__name__ == "MultipleChoiceAnswers"

    # Test summary
    summary = analyzer.summary()
    assert "Favorite color?" in summary
    assert "Multiple Choice" in summary
    assert "Total responses: 5" in summary

    # Test visualization
    viz = analyzer.visualize()
    assert len(viz) > 0

    print("✓ Multiple choice test passed")


def test_numerical():
    """Test numerical analyzer."""
    from edsl.questions import QuestionNumerical
    from edsl.results.by_question.by_question_answers import ByQuestionAnswers

    q = QuestionNumerical(question_name="age", question_text="What is your age?")

    answers = [25, 30, 35, 40, 45]
    analyzer = ByQuestionAnswers.create(q, answers)

    assert analyzer.__class__.__name__ == "NumericalAnswers"

    summary = analyzer.summary()
    assert "Mean: 35.00" in summary
    assert "Median: 35.00" in summary

    viz = analyzer.visualize()
    assert len(viz) > 0

    print("✓ Numerical test passed")


def test_linear_scale():
    """Test linear scale analyzer."""
    from edsl.questions import QuestionLinearScale
    from edsl.results.by_question.by_question_answers import ByQuestionAnswers

    q = QuestionLinearScale(
        question_name="satisfaction",
        question_text="How satisfied?",
        question_options=[1, 2, 3, 4, 5],
    )

    answers = [5, 4, 5, 3, 4, 5]
    analyzer = ByQuestionAnswers.create(q, answers)

    assert analyzer.__class__.__name__ == "LinearScaleAnswers"

    summary = analyzer.summary()
    assert "Linear Scale" in summary
    assert "Total responses: 6" in summary

    print("✓ Linear scale test passed")


def test_checkbox():
    """Test checkbox analyzer."""
    from edsl.questions import QuestionCheckBox
    from edsl.results.by_question.by_question_answers import ByQuestionAnswers

    q = QuestionCheckBox(
        question_name="interests",
        question_text="Select interests",
        question_options=["Sports", "Music", "Reading"],
    )

    answers = [
        ["Sports", "Music"],
        ["Reading"],
        ["Sports", "Reading"],
    ]
    analyzer = ByQuestionAnswers.create(q, answers)

    assert analyzer.__class__.__name__ == "CheckboxAnswers"

    summary = analyzer.summary()
    assert "Checkbox" in summary
    assert "Total respondents: 3" in summary

    print("✓ Checkbox test passed")


def test_free_text():
    """Test free text analyzer."""
    from edsl.questions import QuestionFreeText
    from edsl.results.by_question.by_question_answers import ByQuestionAnswers

    q = QuestionFreeText(question_name="feedback", question_text="Your feedback?")

    answers = ["Great!", "Good service", "Excellent work"]
    analyzer = ByQuestionAnswers.create(q, answers)

    assert analyzer.__class__.__name__ == "FreeTextAnswers"

    summary = analyzer.summary()
    assert "Free Text" in summary
    assert "Total responses: 3" in summary

    print("✓ Free text test passed")


def test_with_none_values():
    """Test handling of None values."""
    from edsl.questions import QuestionMultipleChoice
    from edsl.results.by_question.by_question_answers import ByQuestionAnswers

    q = QuestionMultipleChoice(
        question_name="test", question_text="Test?", question_options=["A", "B"]
    )

    answers = ["A", None, "B", None, "A"]
    analyzer = ByQuestionAnswers.create(q, answers)

    summary = analyzer.summary()
    # Should only count non-None answers
    assert "Total responses: 3" in summary

    print("✓ None value handling test passed")


if __name__ == "__main__":
    print("Running ByQuestionAnswers tests...\n")

    try:
        test_multiple_choice()
        test_numerical()
        test_linear_scale()
        test_checkbox()
        test_free_text()
        test_with_none_values()

        print("\n" + "=" * 50)
        print("All tests passed! ✓")
        print("=" * 50)

    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error running tests: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
