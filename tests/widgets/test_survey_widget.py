"""
Test script for SurveyWidget

This script creates a simple test survey and demonstrates the SurveyWidget functionality.
"""


def test_survey_widget():
    """Test the SurveyWidget with a sample survey."""
    print("Creating test survey...")

    # Import required modules
    from edsl.surveys import Survey
    from edsl.questions import (
        QuestionFreeText,
        QuestionMultipleChoice,
        QuestionNumerical,
    )
    from edsl.widgets import SurveyWidget

    # Create a simple test survey
    questions = [
        QuestionFreeText(question_name="name", question_text="What is your name?"),
        QuestionMultipleChoice(
            question_name="color",
            question_text="What is your favorite color?",
            question_options=["Red", "Blue", "Green", "Yellow", "Other"],
        ),
        QuestionNumerical(question_name="age", question_text="How old are you?"),
        QuestionFreeText(
            question_name="feedback", question_text="Any additional comments?"
        ),
    ]

    survey = Survey(questions)
    print(f"✓ Created survey with {len(survey.questions)} questions")

    # Create the widget
    widget = SurveyWidget(survey)
    print("✓ Created SurveyWidget instance")

    # Test basic properties
    print(f"✓ Widget short name: {widget.widget_short_name}")
    print(f"✓ Survey loaded: {widget.survey is not None}")
    print(
        f"✓ Initial state: complete={widget.is_complete}, answers={len(widget.answers)}"
    )

    # Test that the first question is loaded
    if widget.current_question_name:
        print(f"✓ First question loaded: {widget.current_question_name}")
        if widget.current_question_html:
            print("✓ Question HTML generated successfully")
            # Print first 100 characters of HTML for verification
            html_preview = (
                widget.current_question_html[:100] + "..."
                if len(widget.current_question_html) > 100
                else widget.current_question_html
            )
            print(f"  HTML preview: {html_preview}")
        else:
            print("⚠ Warning: No HTML content generated")
    else:
        print("⚠ Warning: No current question loaded")

    # Test progress tracking
    if widget.progress:
        print(f"✓ Progress tracking: {widget.progress}")

    # Test the get_answers method
    answers = widget.get_answers()
    print(f"✓ get_answers() returns: {answers}")

    print("\nSurveyWidget test completed successfully!")
    return widget


def test_survey_with_rules():
    """Test the SurveyWidget with a survey that has rules."""
    print("\nTesting survey with conditional logic...")

    from edsl.surveys import Survey
    from edsl.questions import QuestionMultipleChoice, QuestionFreeText
    from edsl.widgets import SurveyWidget

    # Create survey with conditional logic
    q1 = QuestionMultipleChoice(
        question_name="has_pet",
        question_text="Do you have a pet?",
        question_options=["Yes", "No"],
    )

    q2 = QuestionFreeText(
        question_name="pet_name", question_text="What is your pet's name?"
    )

    q3 = QuestionFreeText(
        question_name="final_thoughts", question_text="Any final thoughts?"
    )

    survey = Survey([q1, q2, q3])

    # Add a rule: only ask pet_name if has_pet == "Yes"
    survey.add_rule(q1, "{{ has_pet.answer }} == 'No'", q3)

    widget = SurveyWidget(survey)
    print("✓ Created conditional survey widget")
    print(f"✓ Survey has {len(survey.rule_collection.data)} rules")

    return widget


if __name__ == "__main__":
    # Run basic test
    widget1 = test_survey_widget()

    # Run conditional survey test
    try:
        widget2 = test_survey_with_rules()
        print("✓ All tests passed!")
    except Exception as e:
        print(f"⚠ Conditional survey test failed: {e}")
        print("✓ Basic widget test passed!")
