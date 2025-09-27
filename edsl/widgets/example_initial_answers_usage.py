"""
SurveyWidget Initial Answers - Comprehensive Usage Examples

This file provides real-world examples of how to use the initial answers feature
for various scenarios like form auto-fill, session recovery, A/B testing, etc.
"""

def example_user_profile_form():
    """Example: User profile form with auto-fill from existing data."""
    print("Example 1: User Profile Form with Auto-fill")
    print("-" * 50)
    
    from edsl.surveys import Survey
    from edsl.questions import QuestionFreeText, QuestionMultipleChoice, QuestionNumerical
    from edsl.widgets import SurveyWidget
    
    # Create a user profile survey
    profile_questions = [
        QuestionFreeText("first_name", "First name:"),
        QuestionFreeText("last_name", "Last name:"),
        QuestionFreeText("email", "Email address:"),
        QuestionMultipleChoice("country", "Country:", ["USA", "Canada", "UK", "Germany", "France", "Other"]),
        QuestionNumerical("age", "Age:"),
        QuestionMultipleChoice("occupation", "Occupation:", ["Student", "Engineer", "Designer", "Manager", "Other"])
    ]
    
    profile_survey = Survey(profile_questions)
    
    # Simulate existing user data (from database, previous session, etc.)
    existing_user_data = {
        "first_name": "Alice",
        "last_name": "Johnson", 
        "email": "alice.johnson@example.com",
        "country": "USA"
    }
    
    print("Existing user data:", existing_user_data)
    
    # Create widget with pre-filled data
    widget = SurveyWidget(profile_survey, existing_user_data)
    
    print(f"✓ Form starts at: {widget.current_question_name}")
    print(f"✓ Pre-filled fields: {list(existing_user_data.keys())}")
    print(f"✓ Progress: {widget.progress['current']}/{widget.progress['total']}")
    print("User only needs to fill remaining fields: age, occupation\n")
    
    return widget

def example_survey_recovery():
    """Example: Recovering a survey session after interruption."""
    print("Example 2: Survey Recovery After Interruption")
    print("-" * 50)
    
    from edsl.surveys import Survey
    from edsl.questions import QuestionFreeText, QuestionMultipleChoice, QuestionNumerical
    from edsl.widgets import SurveyWidget
    
    # Create a customer feedback survey
    feedback_questions = [
        QuestionFreeText("customer_id", "Customer ID:"),
        QuestionMultipleChoice("product_used", "Which product did you use?", 
                             ["Product A", "Product B", "Product C"]),
        QuestionNumerical("satisfaction", "Rate your satisfaction (1-10):"),
        QuestionMultipleChoice("recommend", "Would you recommend us?", 
                             ["Definitely", "Probably", "Maybe", "Probably not", "Definitely not"]),
        QuestionFreeText("improvements", "What could we improve?"),
        QuestionFreeText("additional_comments", "Additional comments:")
    ]
    
    feedback_survey = Survey(feedback_questions)
    
    # Simulate a session that was interrupted (saved to localStorage, database, etc.)
    interrupted_session = {
        "customer_id": "CUST_12345",
        "product_used": "Product A",
        "satisfaction": 8,
        "recommend": "Probably"
    }
    
    print("Recovered session data:", interrupted_session)
    
    # Resume the survey
    widget = SurveyWidget(feedback_survey, interrupted_session)
    
    print(f"✓ Survey resumed at: {widget.current_question_name}")
    print(f"✓ Recovered answers: {len(interrupted_session)} questions")  
    print(f"✓ Progress: {widget.progress['current']}/{widget.progress['total']}")
    print("User can continue from where they left off\n")
    
    return widget

def example_ab_testing():
    """Example: A/B testing with different survey entry points."""
    print("Example 3: A/B Testing with Different Entry Points")
    print("-" * 50)
    
    from edsl.surveys import Survey
    from edsl.questions import QuestionFreeText, QuestionMultipleChoice
    from edsl.widgets import SurveyWidget
    
    # Create a market research survey
    research_questions = [
        QuestionMultipleChoice("age_group", "Age group:", ["18-24", "25-34", "35-44", "45-54", "55+"]),
        QuestionMultipleChoice("income", "Income level:", ["<$30k", "$30k-$50k", "$50k-$80k", "$80k+"]),
        QuestionMultipleChoice("product_interest", "Interested in:", ["Electronics", "Fashion", "Home", "Sports"]),
        QuestionFreeText("brand_preference", "Preferred brands:"),
        QuestionFreeText("purchase_factors", "What influences your purchases?")
    ]
    
    research_survey = Survey(research_questions)
    
    # A/B Test Variant A: Start with demographics
    print("Variant A: Standard flow (starts with demographics)")
    widget_a = SurveyWidget(research_survey)
    print(f"  Starts at: {widget_a.current_question_name}")
    
    # A/B Test Variant B: Skip demographics for known users
    print("Variant B: Skip demographics for known users")
    known_demographics = {
        "age_group": "25-34",
        "income": "$50k-$80k"
    }
    widget_b = SurveyWidget(research_survey, known_demographics)
    print(f"  Starts at: {widget_b.current_question_name}")
    print(f"  Pre-filled: {list(known_demographics.keys())}")
    
    # A/B Test Variant C: Start with product interest
    print("Variant C: Start with product interest (alternative flow)")
    alternative_start = {"product_interest": "Electronics"}
    widget_c = SurveyWidget(research_survey, alternative_start)
    print(f"  Starts at: {widget_c.current_question_name}")
    print("  Tests if starting with interest improves completion\n")
    
    return widget_a, widget_b, widget_c

def example_survey_templates():
    """Example: Survey templates for testing and demos."""
    print("Example 4: Survey Templates for Testing")
    print("-" * 50)
    
    from edsl.surveys import Survey
    from edsl.questions import QuestionFreeText, QuestionMultipleChoice, QuestionNumerical
    from edsl.widgets import SurveyWidget
    
    # Create an employee satisfaction survey
    employee_questions = [
        QuestionFreeText("employee_id", "Employee ID:"),
        QuestionFreeText("department", "Department:"),
        QuestionNumerical("job_satisfaction", "Job satisfaction (1-10):"),
        QuestionMultipleChoice("work_life_balance", "Work-life balance:", 
                             ["Excellent", "Good", "Fair", "Poor"]),
        QuestionMultipleChoice("career_growth", "Career growth opportunities:", 
                             ["Excellent", "Good", "Fair", "Poor"]),
        QuestionFreeText("suggestions", "Suggestions for improvement:")
    ]
    
    employee_survey = Survey(employee_questions)
    
    # Template 1: Happy employee
    happy_template = {
        "employee_id": "EMP_001",
        "department": "Engineering", 
        "job_satisfaction": 9,
        "work_life_balance": "Excellent",
        "career_growth": "Good",
        "suggestions": "Keep up the great work!"
    }
    
    # Template 2: Dissatisfied employee  
    dissatisfied_template = {
        "employee_id": "EMP_002",
        "department": "Sales",
        "job_satisfaction": 4,
        "work_life_balance": "Poor", 
        "career_growth": "Poor",
        "suggestions": "Need better work-life balance and clearer career paths."
    }
    
    # Template 3: Partial response (for testing incomplete flows)
    partial_template = {
        "employee_id": "EMP_003",
        "department": "Marketing",
        "job_satisfaction": 7
    }
    
    print("Template 1: Happy Employee")
    widget1 = SurveyWidget(employee_survey, happy_template)
    print(f"  Completed: {widget1.is_complete}")
    print(f"  Answers: {len(happy_template)} fields")
    
    print("Template 2: Dissatisfied Employee") 
    widget2 = SurveyWidget(employee_survey, dissatisfied_template)
    print(f"  Completed: {widget2.is_complete}")
    print("  Shows negative feedback pattern")
    
    print("Template 3: Partial Response")
    widget3 = SurveyWidget(employee_survey, partial_template)
    print(f"  Current question: {widget3.current_question_name}")
    print(f"  Progress: {widget3.progress['current']}/{widget3.progress['total']}")
    print("  Use for testing mid-survey interactions\n")
    
    return widget1, widget2, widget3

def example_dynamic_updates():
    """Example: Dynamically updating answers during survey flow."""
    print("Example 5: Dynamic Answer Updates")
    print("-" * 50)
    
    from edsl.surveys import Survey
    from edsl.questions import QuestionFreeText, QuestionMultipleChoice
    from edsl.widgets import SurveyWidget
    
    # Simple survey for demonstration
    dynamic_questions = [
        QuestionFreeText("username", "Username:"),
        QuestionMultipleChoice("plan", "Choose plan:", ["Basic", "Pro", "Enterprise"]),
        QuestionFreeText("promo_code", "Promo code (optional):")
    ]
    
    dynamic_survey = Survey(dynamic_questions)
    
    # Start with empty survey
    widget = SurveyWidget(dynamic_survey)
    print(f"1. Initial state: {widget.current_question_name}")
    
    # Simulate user clicking "Use saved profile" button
    print("2. User clicks 'Use saved profile':")
    saved_profile = {"username": "john_doe_2024"}
    widget.set_initial_answers(saved_profile)
    print(f"   Now at: {widget.current_question_name}")
    
    # Simulate user selecting a promotional plan
    print("3. User selects promotional plan:")
    widget.add_initial_answer("plan", "Pro")
    print(f"   Now at: {widget.current_question_name}")
    
    # Show accumulated state
    print("4. Final state:")
    print(f"   Current answers: {widget.get_answers()}")
    print(f"   Initial answers: {widget.get_initial_answers()}")
    print("   User can complete final field or restart with different data\n")
    
    return widget

def run_all_examples():
    """Run all examples to demonstrate the full feature set."""
    print("SurveyWidget Initial Answers - Real-World Examples")
    print("=" * 60)
    print()
    
    try:
        # Run all examples
        widget1 = example_user_profile_form()
        widget2 = example_survey_recovery() 
        widgets3 = example_ab_testing()
        widgets4 = example_survey_templates()
        widget5 = example_dynamic_updates()
        
        print("Summary of Use Cases:")
        print("=" * 60)
        print("✓ Auto-fill forms with existing user data")
        print("✓ Recover interrupted survey sessions")  
        print("✓ A/B test different survey flows")
        print("✓ Create templates for testing and demos")
        print("✓ Dynamically update answers during flow")
        print()
        print("Integration Patterns:")
        print("- Save answers to localStorage for recovery")
        print("- Pre-fill from user profiles/databases")
        print("- A/B test different entry points") 
        print("- Create demo modes with sample data")
        print("- Allow users to modify previous answers")
        print()
        print("🎉 All examples completed successfully!")
        
        return {
            'profile': widget1,
            'recovery': widget2, 
            'ab_testing': widgets3,
            'templates': widgets4,
            'dynamic': widget5
        }
        
    except Exception as e:
        print(f"❌ Example failed: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    results = run_all_examples()