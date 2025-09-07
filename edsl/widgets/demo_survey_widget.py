"""
Demo script for SurveyWidget

This script demonstrates how to use the SurveyWidget to create interactive surveys.
Run this in a Jupyter notebook to see the widget in action.
"""

def create_demo_survey():
    """Create a demonstration survey for testing the SurveyWidget."""
    from edsl.surveys import Survey
    from edsl.questions import (
        QuestionFreeText, 
        QuestionMultipleChoice, 
        QuestionNumerical,
        QuestionCheckBox
    )
    
    # Create a variety of question types
    questions = [
        QuestionFreeText(
            question_name="user_name",
            question_text="What is your name?"
        ),
        
        QuestionMultipleChoice(
            question_name="experience_level",
            question_text="How would you describe your experience with surveys?",
            question_options=[
                "Beginner - I'm new to this",
                "Intermediate - I have some experience", 
                "Advanced - I'm quite experienced",
                "Expert - I'm very experienced"
            ]
        ),
        
        QuestionNumerical(
            question_name="satisfaction_score",
            question_text="On a scale of 1-10, how satisfied are you with this widget so far?"
        ),
        
        QuestionCheckBox(
            question_name="interests",
            question_text="Which of the following topics interest you? (Select all that apply)",
            question_options=[
                "Data Analysis",
                "Machine Learning", 
                "Survey Research",
                "User Interface Design",
                "Python Programming"
            ]
        ),
        
        QuestionFreeText(
            question_name="feedback_text",
            question_text="Please share any additional feedback or suggestions:"
        )
    ]
    
    return Survey(questions)

def demo_basic_usage():
    """Demonstrate basic SurveyWidget usage."""
    print("=== SurveyWidget Demo ===")
    print("Creating a demo survey...")
    
    # Create the survey
    survey = create_demo_survey()
    print(f"✓ Created survey with {len(survey.questions)} questions")
    
    # Import the widget
    from edsl.widgets import SurveyWidget
    
    # Create the widget
    widget = SurveyWidget(survey)
    print("✓ Created SurveyWidget")
    print(f"✓ Current question: {widget.current_question_name}")
    
    # Show some widget properties
    print(f"✓ Progress: {widget.progress}")
    print(f"✓ Is complete: {widget.is_complete}")
    print(f"✓ Current answers: {widget.get_answers()}")
    
    # Show HTML preview
    if widget.current_question_html:
        preview = widget.current_question_html[:200].replace('\n', ' ')
        print(f"✓ HTML preview: {preview}...")
    
    print("\n=== Usage Instructions ===")
    print("To use this widget in a Jupyter notebook:")
    print("")
    print("1. Create a survey:")
    print("   from edsl.surveys import Survey")
    print("   from edsl.questions import QuestionFreeText, QuestionMultipleChoice")
    print("   from edsl.widgets import SurveyWidget")
    print("")
    print("2. Create your questions and survey:")
    print("   questions = [QuestionFreeText('name', 'What is your name?')]")
    print("   survey = Survey(questions)")
    print("")  
    print("3. Create and display the widget:")
    print("   widget = SurveyWidget(survey)")
    print("   widget  # This will display the interactive widget")
    print("")
    print("4. Access results when complete:")
    print("   answers = widget.get_answers()")
    print("")
    
    return widget

def demo_programmatic_interaction():
    """Demonstrate programmatic interaction with the widget."""
    print("\n=== Programmatic Interaction Demo ===")
    
    from edsl.surveys import Survey
    from edsl.questions import QuestionFreeText, QuestionMultipleChoice
    from edsl.widgets import SurveyWidget
    
    # Create a simple 2-question survey
    questions = [
        QuestionFreeText(
            question_name="demo_name",
            question_text="Enter a test name:"
        ),
        QuestionMultipleChoice(
            question_name="demo_choice",
            question_text="Pick your favorite:",
            question_options=["Option A", "Option B", "Option C"]
        )
    ]
    
    survey = Survey(questions)
    widget = SurveyWidget(survey)
    
    print("✓ Created 2-question demo survey")
    print(f"✓ Starting with question: {widget.current_question_name}")
    
    # Simulate answering the first question
    print("\n1. Simulating answer to first question...")
    widget.submit_answer("Test User")
    print(f"   ✓ Current question: {widget.current_question_name}")
    print(f"   ✓ Answers so far: {widget.get_answers()}")
    
    # Simulate answering the second question
    print("\n2. Simulating answer to second question...")
    widget.submit_answer("Option B")
    print(f"   ✓ Survey complete: {widget.is_complete}")
    print(f"   ✓ Final answers: {widget.get_answers()}")
    
    print("\n✓ Programmatic demo completed!")
    
    return widget

if __name__ == "__main__":
    # Run the demos
    widget1 = demo_basic_usage()
    widget2 = demo_programmatic_interaction()
    
    print("\n=== Demo Complete ===")
    print("The SurveyWidget is ready to use!")
    print("\nIn Jupyter notebook, you can simply display the widget:")
    print("widget = SurveyWidget(your_survey)")
    print("widget")