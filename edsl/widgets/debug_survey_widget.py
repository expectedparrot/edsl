"""
Debug script for SurveyWidget to trace the answer submission process.
"""


def debug_programmatic_interaction():
    """Debug the programmatic interaction to see what's happening."""
    print("=== Debug Programmatic Interaction ===")

    from edsl.surveys import Survey
    from edsl.questions import QuestionFreeText, QuestionMultipleChoice
    from edsl.widgets import SurveyWidget

    # Create a simple 2-question survey
    questions = [
        QuestionFreeText(
            question_name="debug_name", question_text="Enter a test name:"
        ),
        QuestionMultipleChoice(
            question_name="debug_choice",
            question_text="Pick your favorite:",
            question_options=["Option A", "Option B", "Option C"],
        ),
    ]

    survey = Survey(questions)
    widget = SurveyWidget(survey)

    print("✓ Created 2-question debug survey")
    print(f"✓ Starting with question: {widget.current_question_name}")
    print(f"✓ Initial answers: {widget.get_answers()}")

    # Answer the first question
    print("\n1. Answering first question with 'Debug User'...")
    widget.submit_answer("Debug User")
    print(f"   ✓ Current question: {widget.current_question_name}")
    print(f"   ✓ Answers after first submission: {widget.get_answers()}")
    print(f"   ✓ Survey complete: {widget.is_complete}")

    if not widget.is_complete and widget.current_question_name == "debug_choice":
        # Answer the second question
        print("\n2. Answering second question with 'Option B'...")
        widget.submit_answer("Option B")
        print(f"   ✓ Current question: {widget.current_question_name}")
        print(f"   ✓ Answers after second submission: {widget.get_answers()}")
        print(f"   ✓ Survey complete: {widget.is_complete}")
    else:
        print("\n⚠ Issue: Survey completed early or wrong question")

    print(f"\n✓ Final state: Complete={widget.is_complete}")
    print(f"✓ Final answers: {widget.get_answers()}")

    return widget


if __name__ == "__main__":
    debug_programmatic_interaction()
