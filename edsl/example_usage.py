#!/usr/bin/env python3
"""
Example usage of the EDSL to SurveyJS converter.
"""
import json
from edsl import (
    QuestionFreeText, 
    QuestionMultipleChoice, 
    QuestionCheckBox, 
    QuestionNumerical, 
    QuestionYesNo,
    QuestionLikertFive,
    QuestionLinearScale,
    Survey
)
from surveyjs_converter import convert_edsl_to_surveyjs

def create_comprehensive_survey():
    """Create a comprehensive survey with various question types."""
    
    questions = [
        # Basic text input
        QuestionFreeText(
            question_name="full_name",
            question_text="Please enter your full name"
        ),
        
        # Multiple choice with single selection
        QuestionMultipleChoice(
            question_name="experience_level",
            question_text="What is your experience level with surveys?",
            question_options=["Beginner", "Intermediate", "Advanced", "Expert"]
        ),
        
        # Checkbox for multiple selections
        QuestionCheckBox(
            question_name="interests",
            question_text="Which topics are you interested in? (Select all that apply)",
            question_options=[
                "Technology", 
                "Science", 
                "Arts", 
                "Sports", 
                "Business",
                "Education",
                "Healthcare"
            ]
        ),
        
        # Numerical input
        QuestionNumerical(
            question_name="years_experience",
            question_text="How many years of relevant experience do you have?"
        ),
        
        # Yes/No question
        QuestionYesNo(
            question_name="subscribe_updates",
            question_text="Would you like to receive updates about new features?"
        ),
        
        # Likert scale
        QuestionLikertFive(
            question_name="satisfaction",
            question_text="I am satisfied with the current survey tools available."
        ),
        
        # Linear scale/rating
        QuestionLinearScale(
            question_name="recommendation",
            question_text="How likely are you to recommend this tool to others?",
            question_options=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            option_labels={1: "Not at all likely", 10: "Extremely likely"}
        ),
        
        # Free text for feedback
        QuestionFreeText(
            question_name="additional_comments",
            question_text="Please share any additional comments or suggestions"
        )
    ]
    
    return Survey(questions)

def main():
    """Main function to demonstrate the conversion."""
    print("Creating comprehensive EDSL survey...")
    survey = create_comprehensive_survey()
    
    print(f"Survey created with {len(survey.questions)} questions")
    
    print("\nConverting to SurveyJS format...")
    surveyjs_json = convert_edsl_to_surveyjs(
        survey, 
        title="Comprehensive Survey Example"
    )
    
    print("\nSurveyJS JSON structure:")
    print(f"- Title: {surveyjs_json['title']}")
    print(f"- Pages: {len(surveyjs_json['pages'])}")
    print(f"- Questions: {len(surveyjs_json['pages'][0]['elements'])}")
    
    print("\nQuestion types in SurveyJS format:")
    for i, element in enumerate(surveyjs_json['pages'][0]['elements'], 1):
        print(f"{i}. {element['name']}: {element['type']}")
    
    # Save the complete example
    with open('comprehensive_survey.json', 'w') as f:
        json.dump(surveyjs_json, f, indent=2)
    
    print(f"\n📄 Comprehensive survey saved to: comprehensive_survey.json")
    
    # Create TypeScript version
    ts_content = f"""// Comprehensive SurveyJS JSON from EDSL Survey
export const comprehensiveSurveyJson = {json.dumps(surveyjs_json, indent=2)};
"""
    
    with open('comprehensive_survey.ts', 'w') as f:
        f.write(ts_content)
    
    print(f"📄 TypeScript version saved to: comprehensive_survey.ts")

if __name__ == "__main__":
    main()