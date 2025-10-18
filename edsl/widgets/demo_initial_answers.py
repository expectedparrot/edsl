"""
Demo script for SurveyWidget Initial Answers Feature

This script demonstrates the new functionality that allows you to pass 
an initial answers dictionary to resume a survey from a previous state.
"""


def demo_resume_survey():
    """Demonstrate resuming a survey from previous answers."""
    print("=== Demo: Resume Survey from Previous State ===")

    from edsl.surveys import Survey
    from edsl.questions import (
        QuestionFreeText,
        QuestionMultipleChoice,
        QuestionNumerical,
    )
    from edsl.widgets import SurveyWidget

    # Create a comprehensive survey
    questions = [
        QuestionFreeText(
            question_name="participant_name", question_text="What is your full name?"
        ),
        QuestionMultipleChoice(
            question_name="experience_level",
            question_text="What is your experience level with surveys?",
            question_options=["Beginner", "Intermediate", "Advanced", "Expert"],
        ),
        QuestionNumerical(
            question_name="satisfaction_rating",
            question_text="Rate your satisfaction with this widget (1-10):",
        ),
        QuestionMultipleChoice(
            question_name="recommendation",
            question_text="Would you recommend this widget to others?",
            question_options=[
                "Definitely",
                "Probably",
                "Maybe",
                "Probably not",
                "Definitely not",
            ],
        ),
        QuestionFreeText(
            question_name="improvement_suggestions",
            question_text="What improvements would you suggest?",
        ),
    ]

    survey = Survey(questions)
    print(f"✓ Created survey with {len(questions)} questions")

    # Scenario 1: User starts fresh
    print("\n1. Starting fresh (no previous answers):")
    widget_fresh = SurveyWidget(survey)
    print(f"   First question: {widget_fresh.current_question_name}")
    print(
        f"   Progress: {widget_fresh.progress['current']}/{widget_fresh.progress['total']}"
    )

    # Scenario 2: User returns after answering first 2 questions
    print("\n2. Resuming after answering first 2 questions:")
    previous_answers = {
        "participant_name": "Alice Johnson",
        "experience_level": "Intermediate",
    }
    widget_resumed = SurveyWidget(survey, previous_answers)
    print(f"   Current question: {widget_resumed.current_question_name}")
    print(f"   Previous answers loaded: {widget_resumed.get_answers()}")
    print(
        f"   Progress: {widget_resumed.progress['current']}/{widget_resumed.progress['total']}"
    )

    # Scenario 3: User returns near the end
    print("\n3. Resuming near the end (4 out of 5 questions answered):")
    near_complete_answers = {
        "participant_name": "Bob Smith",
        "experience_level": "Advanced",
        "satisfaction_rating": 9,
        "recommendation": "Definitely",
    }
    widget_near_end = SurveyWidget(survey, near_complete_answers)
    print(f"   Current question: {widget_near_end.current_question_name}")
    print(
        f"   Previous answers: {len(widget_near_end.get_answers())} questions answered"
    )
    print(
        f"   Progress: {widget_near_end.progress['current']}/{widget_near_end.progress['total']}"
    )

    # Scenario 4: All questions already answered
    print("\n4. All questions already answered:")
    complete_answers = {
        "participant_name": "Carol Davis",
        "experience_level": "Expert",
        "satisfaction_rating": 10,
        "recommendation": "Definitely",
        "improvement_suggestions": "Add more question types!",
    }
    widget_complete = SurveyWidget(survey, complete_answers)
    print(f"   Survey completed: {widget_complete.is_complete}")
    print(f"   All answers: {widget_complete.get_answers()}")

    return widget_fresh, widget_resumed, widget_near_end, widget_complete


def demo_conditional_survey_resume():
    """Demonstrate resuming conditional surveys with branching logic."""
    print("\n=== Demo: Resume Conditional Survey ===")

    from edsl.surveys import Survey
    from edsl.questions import (
        QuestionMultipleChoice,
        QuestionFreeText,
        QuestionNumerical,
    )
    from edsl.widgets import SurveyWidget

    # Create a survey with conditional branching
    q1 = QuestionMultipleChoice(
        question_name="user_type",
        question_text="What type of user are you?",
        question_options=["Student", "Professional", "Researcher", "Other"],
    )

    q2_student = QuestionFreeText(
        question_name="school_name", question_text="What school do you attend?"
    )

    q2_professional = QuestionFreeText(
        question_name="company_name", question_text="What company do you work for?"
    )

    q3 = QuestionNumerical(
        question_name="years_experience",
        question_text="How many years of experience do you have?",
    )

    q4 = QuestionFreeText(
        question_name="final_thoughts", question_text="Any final thoughts?"
    )

    survey = Survey([q1, q2_student, q2_professional, q3, q4])

    # Add conditional rules
    # If Student, go to school_name, skip company_name
    survey.add_rule(q1, "{{ user_type.answer }} == 'Student'", q2_student)
    survey.add_rule(q2_student, "True", q3)  # From school_name, go to years_experience

    # If Professional, go to company_name, skip school_name
    survey.add_rule(q1, "{{ user_type.answer }} == 'Professional'", q2_professional)
    survey.add_rule(
        q2_professional, "True", q3
    )  # From company_name, go to years_experience

    # If Researcher or Other, skip both school and company questions
    survey.add_rule(q1, "{{ user_type.answer }} in ['Researcher', 'Other']", q3)

    print(f"✓ Created conditional survey with {len(survey.rule_collection.data)} rules")

    # Test different resume scenarios based on user type

    print("\n1. Resume as Student (should continue with school question):")
    student_answers = {"user_type": "Student"}
    widget_student = SurveyWidget(survey, student_answers)
    print(f"   Next question: {widget_student.current_question_name}")
    print(f"   Answers: {widget_student.get_answers()}")

    print("\n2. Resume as Professional (should continue with company question):")
    professional_answers = {"user_type": "Professional"}
    widget_professional = SurveyWidget(survey, professional_answers)
    print(f"   Next question: {widget_professional.current_question_name}")
    print(f"   Answers: {widget_professional.get_answers()}")

    print("\n3. Resume as Researcher (should skip to experience question):")
    researcher_answers = {"user_type": "Researcher"}
    widget_researcher = SurveyWidget(survey, researcher_answers)
    print(f"   Next question: {widget_researcher.current_question_name}")
    print(f"   Answers: {widget_researcher.get_answers()}")

    print("\n4. Resume Student who already answered school question:")
    student_complete_answers = {
        "user_type": "Student",
        "school_name": "University of Example",
    }
    widget_student_advanced = SurveyWidget(survey, student_complete_answers)
    print(f"   Next question: {widget_student_advanced.current_question_name}")
    print(f"   Answers: {widget_student_advanced.get_answers()}")

    return (
        widget_student,
        widget_professional,
        widget_researcher,
        widget_student_advanced,
    )


def demo_dynamic_answer_updates():
    """Demonstrate updating initial answers after widget creation."""
    print("\n=== Demo: Dynamic Answer Updates ===")

    from edsl.surveys import Survey
    from edsl.questions import QuestionFreeText, QuestionMultipleChoice
    from edsl.widgets import SurveyWidget

    # Simple 3-question survey
    questions = [
        QuestionFreeText("q1", "Question 1: Your name?"),
        QuestionMultipleChoice(
            "q2", "Question 2: Pick a color:", ["Red", "Green", "Blue"]
        ),
        QuestionFreeText("q3", "Question 3: Your thoughts?"),
    ]

    survey = Survey(questions)

    # Start with empty widget
    widget = SurveyWidget(survey)
    print("1. Starting with no initial answers:")
    print(f"   Current question: {widget.current_question_name}")
    print(f"   Answers: {widget.get_answers()}")

    # Add first answer dynamically
    print("\n2. Adding first answer dynamically:")
    widget.set_initial_answers({"q1": "Dynamic User"})
    print(f"   Current question: {widget.current_question_name}")
    print(f"   Answers: {widget.get_answers()}")

    # Add second answer
    print("\n3. Adding second answer:")
    widget.add_initial_answer("q2", "Green")
    print(f"   Current question: {widget.current_question_name}")
    print(f"   Answers: {widget.get_answers()}")
    print(f"   Initial answers stored: {widget.get_initial_answers()}")

    # Reset to different initial state
    print("\n4. Resetting to different initial answers:")
    widget.set_initial_answers(
        {"q1": "Another User", "q2": "Blue", "q3": "Almost done!"}
    )
    print(f"   Survey completed: {widget.is_complete}")
    print(f"   All answers: {widget.get_answers()}")

    return widget


def demo_practical_use_cases():
    """Show practical use cases for the initial answers feature."""
    print("\n=== Demo: Practical Use Cases ===")

    from edsl.surveys import Survey
    from edsl.questions import (
        QuestionFreeText,
        QuestionMultipleChoice,
        QuestionNumerical,
    )
    from edsl.widgets import SurveyWidget

    # Create a user registration/profile survey
    questions = [
        QuestionFreeText("username", "Choose a username:"),
        QuestionFreeText("email", "Enter your email:"),
        QuestionMultipleChoice(
            "country", "Select your country:", ["USA", "Canada", "UK", "Other"]
        ),
        QuestionNumerical("age", "Enter your age:"),
        QuestionMultipleChoice(
            "interests",
            "Primary interest:",
            ["Technology", "Science", "Arts", "Business"],
        ),
    ]

    survey = Survey(questions)

    print("Use Case 1: Form Auto-fill")
    print("- Pre-populate form with known user data")
    known_data = {"username": "user123", "email": "user@example.com"}
    widget1 = SurveyWidget(survey, known_data)
    print(f"   Starting at: {widget1.current_question_name} (demographic info)")
    print(f"   Pre-filled: {list(known_data.keys())}")

    print("\nUse Case 2: Survey Recovery")
    print("- User's browser crashed, recover their progress")
    crashed_session = {
        "username": "recovered_user",
        "email": "recover@example.com",
        "country": "Canada",
        "age": 25,
    }
    widget2 = SurveyWidget(survey, crashed_session)
    print(f"   Recovered to: {widget2.current_question_name} (final question)")
    print(f"   Recovered {len(crashed_session)} previous answers")

    print("\nUse Case 3: A/B Testing")
    print("- Test different starting points in survey flow")
    a_test_start = {"country": "USA"}  # Start demo user in USA flow
    widget3 = SurveyWidget(survey, a_test_start)
    print(f"   A/B test variant starting at: {widget3.current_question_name}")

    print("\nUse Case 4: Survey Templates")
    print("- Pre-fill common responses for quick testing")
    template_answers = {
        "username": "test_user_001",
        "email": "test@company.com",
        "country": "USA",
        "age": 30,
        "interests": "Technology",
    }
    widget4 = SurveyWidget(survey, template_answers)
    print(f"   Template completed survey: {widget4.is_complete}")
    print("   Use for: testing, demos, default responses")

    return widget1, widget2, widget3, widget4


if __name__ == "__main__":
    print("SurveyWidget Initial Answers - Feature Demonstration")
    print("=" * 60)

    try:
        # Run all demos
        widgets1 = demo_resume_survey()
        widgets2 = demo_conditional_survey_resume()
        widget3 = demo_dynamic_answer_updates()
        widgets4 = demo_practical_use_cases()

        print("\n" + "=" * 60)
        print("🎉 All demos completed successfully!")
        print("\nKey Features Demonstrated:")
        print("✓ Resume surveys from any point")
        print("✓ Handle conditional/branching surveys")
        print("✓ Update initial answers dynamically")
        print("✓ Practical use cases: auto-fill, recovery, A/B testing")
        print("\nUsage:")
        print("  # Basic usage")
        print("  widget = SurveyWidget(survey, {'question1': 'answer1'})")
        print("  ")
        print("  # Dynamic updates")
        print("  widget.set_initial_answers({'q1': 'new_answer'})")
        print("  widget.add_initial_answer('q2', 'another_answer')")

    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback

        traceback.print_exc()
