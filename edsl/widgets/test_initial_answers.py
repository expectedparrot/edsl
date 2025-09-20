"""
Test script for SurveyWidget initial answers feature

This script tests the new functionality that allows passing initial answers 
to resume a survey from a previous state.
"""

def test_initial_answers_basic():
    """Test basic initial answers functionality."""
    print("=== Testing Initial Answers - Basic ===")
    
    from edsl.surveys import Survey
    from edsl.questions import QuestionFreeText, QuestionMultipleChoice, QuestionNumerical
    from edsl.widgets import SurveyWidget
    
    # Create a 4-question survey
    questions = [
        QuestionFreeText(
            question_name="user_name",
            question_text="What is your name?"
        ),
        QuestionMultipleChoice(
            question_name="user_color",
            question_text="What is your favorite color?",
            question_options=["Red", "Blue", "Green", "Yellow"]
        ),
        QuestionNumerical(
            question_name="user_age",
            question_text="How old are you?"
        ),
        QuestionFreeText(
            question_name="user_feedback",
            question_text="Any final comments?"
        )
    ]
    
    survey = Survey(questions)
    print(f"✓ Created survey with {len(questions)} questions")
    
    # Test 1: No initial answers (baseline)
    widget1 = SurveyWidget(survey)
    print(f"✓ Widget without initial answers starts at: {widget1.current_question_name}")
    print(f"  Current answers: {widget1.get_answers()}")
    print(f"  Progress: {widget1.progress}")
    
    # Test 2: With initial answers for first question
    initial_answers_1 = {"user_name": "Alice"}
    widget2 = SurveyWidget(survey, initial_answers_1)
    print(f"✓ Widget with 1 initial answer starts at: {widget2.current_question_name}")
    print(f"  Current answers: {widget2.get_answers()}")
    print(f"  Progress: {widget2.progress}")
    
    # Test 3: With initial answers for first two questions
    initial_answers_2 = {
        "user_name": "Bob", 
        "user_color": "Blue"
    }
    widget3 = SurveyWidget(survey, initial_answers_2)
    print(f"✓ Widget with 2 initial answers starts at: {widget3.current_question_name}")
    print(f"  Current answers: {widget3.get_answers()}")
    print(f"  Progress: {widget3.progress}")
    
    # Test 4: With initial answers for all questions (should complete survey)
    initial_answers_all = {
        "user_name": "Charlie",
        "user_color": "Green", 
        "user_age": 30,
        "user_feedback": "Great survey!"
    }
    widget4 = SurveyWidget(survey, initial_answers_all)
    print(f"✓ Widget with all initial answers - completed: {widget4.is_complete}")
    print(f"  Final answers: {widget4.get_answers()}")
    print(f"  Progress: {widget4.progress}")
    
    return widget1, widget2, widget3, widget4

def test_initial_answers_conditional():
    """Test initial answers with conditional survey logic."""
    print("\n=== Testing Initial Answers - Conditional Survey ===")
    
    from edsl.surveys import Survey
    from edsl.questions import QuestionMultipleChoice, QuestionFreeText
    from edsl.widgets import SurveyWidget
    
    # Create survey with conditional logic
    q1 = QuestionMultipleChoice(
        question_name="has_pet",
        question_text="Do you have a pet?",
        question_options=["Yes", "No"]
    )
    
    q2 = QuestionFreeText(
        question_name="pet_name",
        question_text="What is your pet's name?"
    )
    
    q3 = QuestionFreeText(
        question_name="final_thoughts",
        question_text="Any final thoughts?"
    )
    
    survey = Survey([q1, q2, q3])
    # Add rule: skip pet_name if has_pet == "No"
    survey.add_rule(q1, "{{ has_pet.answer }} == 'No'", q3)
    
    print(f"✓ Created conditional survey with {len(survey.rule_collection.data)} rules")
    
    # Test path 1: Answer "Yes" to pet question
    initial_answers_yes = {"has_pet": "Yes"}
    widget_yes = SurveyWidget(survey, initial_answers_yes)
    print(f"✓ With 'Yes' answer, next question is: {widget_yes.current_question_name}")
    print(f"  Answers: {widget_yes.get_answers()}")
    
    # Test path 2: Answer "No" to pet question (should skip pet_name)
    initial_answers_no = {"has_pet": "No"}
    widget_no = SurveyWidget(survey, initial_answers_no)
    print(f"✓ With 'No' answer, next question is: {widget_no.current_question_name}")
    print(f"  Answers: {widget_no.get_answers()}")
    
    return widget_yes, widget_no

def test_set_initial_answers():
    """Test setting initial answers after widget creation."""
    print("\n=== Testing Set Initial Answers ===")
    
    from edsl.surveys import Survey
    from edsl.questions import QuestionFreeText, QuestionMultipleChoice
    from edsl.widgets import SurveyWidget
    
    questions = [
        QuestionFreeText("q1", "Question 1?"),
        QuestionMultipleChoice("q2", "Question 2?", ["A", "B", "C"]),
        QuestionFreeText("q3", "Question 3?")
    ]
    
    survey = Survey(questions)
    
    # Create widget without initial answers
    widget = SurveyWidget(survey)
    print(f"✓ Initial state: question={widget.current_question_name}, answers={widget.get_answers()}")
    
    # Set initial answers using method
    widget.set_initial_answers({"q1": "Answer 1"})
    print(f"✓ After set_initial_answers: question={widget.current_question_name}, answers={widget.get_answers()}")
    
    # Add another initial answer
    widget.add_initial_answer("q2", "B")
    print(f"✓ After add_initial_answer: question={widget.current_question_name}, answers={widget.get_answers()}")
    
    # Check initial answers
    print(f"✓ Initial answers stored: {widget.get_initial_answers()}")
    
    return widget

def test_programmatic_completion():
    """Test completing a survey that was started with initial answers."""
    print("\n=== Testing Programmatic Completion ===")
    
    from edsl.surveys import Survey
    from edsl.questions import QuestionFreeText, QuestionMultipleChoice
    from edsl.widgets import SurveyWidget
    
    questions = [
        QuestionFreeText("name", "Your name?"),
        QuestionMultipleChoice("choice", "Pick one:", ["Option A", "Option B"]),
        QuestionFreeText("feedback", "Comments?")
    ]
    
    survey = Survey(questions)
    
    # Start with initial answer for first question
    widget = SurveyWidget(survey, {"name": "Test User"})
    print(f"✓ Started with name pre-filled, current: {widget.current_question_name}")
    print(f"  Answers: {widget.get_answers()}")
    
    # Complete the remaining questions
    if widget.current_question_name == "choice":
        widget.submit_answer("Option A")
        print(f"✓ After submitting choice, current: {widget.current_question_name}")
        print(f"  Answers: {widget.get_answers()}")
    
    if widget.current_question_name == "feedback":
        widget.submit_answer("All good!")
        print(f"✓ After submitting feedback, completed: {widget.is_complete}")
        print(f"  Final answers: {widget.get_answers()}")
    
    return widget

if __name__ == "__main__":
    # Run all tests
    print("Testing SurveyWidget Initial Answers Feature")
    print("=" * 50)
    
    try:
        widgets1 = test_initial_answers_basic()
        widgets2 = test_initial_answers_conditional() 
        widget3 = test_set_initial_answers()
        widget4 = test_programmatic_completion()
        
        print("\n" + "=" * 50)
        print("✅ All initial answers tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()