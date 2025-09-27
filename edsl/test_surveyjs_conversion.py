#!/usr/bin/env python3
"""
Test script to verify the EDSL to SurveyJS conversion works correctly.
"""
import json
from edsl import QuestionFreeText, QuestionMultipleChoice, QuestionCheckBox, QuestionNumerical, QuestionYesNo, Survey
from surveyjs_converter import convert_edsl_to_surveyjs

def test_conversion():
    """Test the conversion of various question types."""
    
    # Create sample questions of different types
    questions = [
        QuestionFreeText(
            question_name="name",
            question_text="What is your name?"
        ),
        
        QuestionMultipleChoice(
            question_name="favorite_color",
            question_text="What is your favorite color?",
            question_options=["Red", "Blue", "Green", "Yellow"]
        ),
        
        QuestionCheckBox(
            question_name="hobbies",
            question_text="What are your hobbies? (Select all that apply)",
            question_options=["Reading", "Sports", "Music", "Gaming", "Travel"]
        ),
        
        QuestionNumerical(
            question_name="age",
            question_text="What is your age?"
        ),
        
        QuestionYesNo(
            question_name="newsletter",
            question_text="Would you like to receive our newsletter?"
        )
    ]
    
    # Create survey
    survey = Survey(questions)
    
    # Convert to SurveyJS format
    surveyjs_json = convert_edsl_to_surveyjs(survey, "Test Survey")
    
    # Print the converted JSON
    print("Converted SurveyJS JSON:")
    print("=" * 50)
    print(json.dumps(surveyjs_json, indent=2))
    
    # Validate the conversion
    assert "title" in surveyjs_json
    assert "pages" in surveyjs_json
    assert len(surveyjs_json["pages"]) == 1
    assert "elements" in surveyjs_json["pages"][0]
    assert len(surveyjs_json["pages"][0]["elements"]) == len(questions)
    
    # Check each converted question
    elements = surveyjs_json["pages"][0]["elements"]
    
    # Free text question
    assert elements[0]["type"] == "text"
    assert elements[0]["name"] == "name"
    assert elements[0]["title"] == "What is your name?"
    
    # Multiple choice question
    assert elements[1]["type"] == "radiogroup"
    assert elements[1]["name"] == "favorite_color"
    assert len(elements[1]["choices"]) == 4
    
    # Checkbox question
    assert elements[2]["type"] == "checkbox"
    assert elements[2]["name"] == "hobbies"
    assert len(elements[2]["choices"]) == 5
    
    # Numerical question
    assert elements[3]["type"] == "text"
    assert elements[3]["inputType"] == "number"
    assert elements[3]["name"] == "age"
    
    # Yes/No question
    assert elements[4]["type"] == "boolean"
    assert elements[4]["name"] == "newsletter"
    
    print("\n✅ All conversion tests passed!")
    
    return surveyjs_json

def create_sample_json_file():
    """Create a sample JSON file that can be used in React."""
    surveyjs_json = test_conversion()
    
    # Write to a JSON file
    with open('sample_survey.json', 'w') as f:
        json.dump(surveyjs_json, f, indent=2)
    
    print("\n📄 Sample survey JSON saved to: sample_survey.json")
    
    # Also create a JavaScript/TypeScript module
    js_content = f"""// Auto-generated SurveyJS JSON from EDSL Survey
export const sampleSurveyJson = {json.dumps(surveyjs_json, indent=2)};
"""
    
    with open('sample_survey.ts', 'w') as f:
        f.write(js_content)
    
    print("📄 Sample survey TypeScript module saved to: sample_survey.ts")

if __name__ == "__main__":
    create_sample_json_file()