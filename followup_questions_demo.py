"""
Demonstration of the add_followup_questions() method

This demonstrates the new syntactical sugar feature for adding follow-up questions
based on multiple choice or checkbox question options, as requested in GitHub issue #2231.
"""

from edsl import QuestionMultipleChoice, QuestionFreeText, Survey

# Create a multiple choice question
q_restaurants = QuestionMultipleChoice(
    question_name="restaurants",
    question_text="Which type of restaurant do you prefer?",
    question_options=["Italian", "Chinese", "Mexican", "Indian"]
)

# Create a follow-up question template
# The {{ restaurants.answer }} will be replaced with each option
q_followup = QuestionFreeText(
    question_name="why_restaurant",
    question_text="Why do you like {{ restaurants.answer }} food?"
)

# Create a final question
q_overall = QuestionFreeText(
    question_name="overall_feedback",
    question_text="Any other comments about restaurants?"
)

# Build the survey with automatic follow-ups
survey = Survey([q_restaurants, q_overall]).add_followup_questions("restaurants", q_followup)

print("="*70)
print("Survey Structure with Follow-up Questions")
print("="*70)
print("\nQuestions in the survey:")
for i, q in enumerate(survey.questions):
    print(f"{i}. {q.question_name}")
    print(f"   {q.question_text}")

print("\n" + "="*70)
print("Survey Flow Demonstration")
print("="*70)

# Demonstrate the flow for different answers
test_cases = ["Italian", "Chinese", "Mexican", "Indian"]

for answer in test_cases:
    print(f"\n--- When user selects '{answer}' ---")
    current = None
    answers = {}
    step = 0

    # Simulate going through the survey
    questions_shown = []
    while step < 10:  # Safety limit
        from edsl.surveys.base import EndOfSurvey

        next_q = survey.next_question(current, answers)

        # Check if we've reached the end
        if next_q == EndOfSurvey or (hasattr(next_q, '__class__') and
                                      next_q.__class__.__name__ == 'EndOfSurveyParent'):
            break

        questions_shown.append(next_q.question_name)

        # Simulate answering
        if next_q.question_name == "restaurants":
            answers["restaurants.answer"] = answer
        elif next_q.question_name.startswith("why_restaurant"):
            answers[f"{next_q.question_name}.answer"] = "Sample answer"
        elif next_q.question_name == "overall_feedback":
            answers["overall_feedback.answer"] = "Great!"

        current = next_q.question_name
        step += 1

    print(f"Questions shown: {' -> '.join(questions_shown)}")

print("\n" + "="*70)
print("\nKey Features:")
print("- Automatically creates one follow-up question per option")
print("- Substitutes {{ restaurants.answer }} with the actual option text")
print("- Adds skip logic so each follow-up only shows for its option")
print("- Maintains proper survey flow to the next question after follow-ups")
print("\nThis eliminates the need for manually creating and wiring up")
print("conditional follow-up questions for each option!")
print("="*70)
