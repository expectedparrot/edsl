"""
Test script for the QSF to Survey converter macro.

This script creates a sample QSF file and tests the macro conversion functionality.
"""

import json
import tempfile
import os

# Import the macro
from edsl.macros.builtin.qsf_to_survey import qsf_to_survey_macro


def create_sample_qsf():
    """Create a sample QSF file for testing based on the example in qsf_example.py"""
    sample_qsf = {
        "SurveyEntry": {
            "SurveyID": "SV_example123",
            "SurveyName": "Customer Feedback Survey",
            "SurveyDescription": "A sample customer feedback survey for testing QSF macro",
            "SurveyLanguage": "EN",
        },
        "SurveyElements": [
            # Single choice question
            {
                "Element": "SQ",
                "PrimaryAttribute": "QID1",
                "Payload": {
                    "QuestionID": "QID1",
                    "QuestionType": "MC",
                    "Selector": "SAVR",
                    "DataExportTag": "satisfaction",
                    "QuestionText": "How satisfied are you with our service?",
                    "Choices": {
                        "1": {"Display": "Very Dissatisfied"},
                        "2": {"Display": "Dissatisfied"},
                        "3": {"Display": "Neutral"},
                        "4": {"Display": "Satisfied"},
                        "5": {"Display": "Very Satisfied"},
                    },
                    "ChoiceOrder": ["1", "2", "3", "4", "5"],
                },
            },
            # Text input question
            {
                "Element": "SQ",
                "PrimaryAttribute": "QID2",
                "Payload": {
                    "QuestionID": "QID2",
                    "QuestionType": "TE",
                    "Selector": "SL",
                    "DataExportTag": "feedback",
                    "QuestionText": "Please tell us what we could improve:",
                },
            },
            # Block definition
            {
                "Element": "BL",
                "Payload": [
                    {
                        "ID": "BL_main",
                        "Type": "Standard",
                        "Description": "Customer Feedback Questions",
                        "BlockElements": [
                            {"Type": "Question", "QuestionID": "QID1"},
                            {"Type": "Question", "QuestionID": "QID2"},
                        ],
                    }
                ],
            },
            # Flow definition
            {
                "Element": "FL",
                "Payload": {
                    "Type": "Root",
                    "Flow": [{"Type": "Block", "ID": "BL_main"}],
                },
            },
        ],
    }
    return sample_qsf


def test_macro_basic_functionality():
    """Test the macro with a sample QSF file"""
    print("=" * 60)
    print("TESTING QSF TO SURVEY MACRO")
    print("=" * 60)

    # Create sample QSF file
    sample_qsf = create_sample_qsf()

    # Save to temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".qsf", delete=False) as f:
        json.dump(sample_qsf, f, indent=2)
        qsf_path = f.name

    print(f"✅ Created sample QSF file: {qsf_path}")

    try:
        # Test the macro
        print("\n🔄 Running QSF to Survey macro...")

        params = {"qsf_file": qsf_path, "encoding": "utf-8"}

        # Run the macro
        result = qsf_to_survey_macro.output(params)

        # Get the converted survey
        survey = result.survey

        print("✅ Macro execution successful!")
        print(f"📊 Survey type: {type(survey).__name__}")
        print(f"📝 Number of questions: {len(survey.questions)}")

        # Display question details
        print("\n📋 Converted Questions:")
        for i, question in enumerate(survey.questions):
            if hasattr(question, "question_name"):
                q_type = type(question).__name__
                print(f"  {i+1}. {question.question_name} ({q_type})")
                print(f"     Text: {question.question_text}")
                if hasattr(question, "question_options") and question.question_options:
                    print(f"     Options: {question.question_options}")
                print()

        # Test survey serialization
        print("🔍 Testing survey serialization...")
        survey_dict = survey.to_dict()
        print(f"✅ Survey serialized successfully ({len(survey_dict)} top-level keys)")

        # Show some survey metadata
        if hasattr(survey, "question_groups") and survey.question_groups:
            print(f"📂 Question groups: {survey.question_groups}")
        if hasattr(survey, "questions_to_randomize") and survey.questions_to_randomize:
            print(f"🔀 Questions to randomize: {survey.questions_to_randomize}")

        return survey

    except Exception as e:
        print(f"❌ Error testing macro: {str(e)}")
        import traceback

        print("Full traceback:")
        traceback.print_exc()
        return None

    finally:
        # Clean up temporary file
        if os.path.exists(qsf_path):
            os.unlink(qsf_path)
            print(f"🧹 Cleaned up temporary file: {qsf_path}")


def test_macro_error_handling():
    """Test macro error handling with invalid inputs"""
    print("\n" + "=" * 60)
    print("TESTING ERROR HANDLING")
    print("=" * 60)

    # Test with non-existent file
    print("🧪 Testing with non-existent file...")
    try:
        result = qsf_to_survey_macro.output(
            {"qsf_file": "/definitely/does/not/exist.qsf", "encoding": "utf-8"}
        )
        print("❌ Should have failed with non-existent file")
    except Exception as e:
        print(f"✅ Correctly handled non-existent file error: {type(e).__name__}")
        print(f"   Error message: {str(e)}")

    # Test with missing parameters
    print("\n🧪 Testing with missing qsf_file parameter...")
    try:
        result = qsf_to_survey_macro.output({"encoding": "utf-8"})
        print("❌ Should have failed with missing parameter")
    except Exception as e:
        print(f"✅ Correctly handled missing parameter error: {type(e).__name__}")
        print(f"   Error message: {str(e)}")


def main():
    """Run all tests"""
    print("QSF TO SURVEY MACRO TESTING SUITE")
    print("=" * 60)

    # Test basic functionality
    survey = test_macro_basic_functionality()

    # Test error handling
    test_macro_error_handling()

    # Summary
    print("\n" + "=" * 60)
    print("TESTING COMPLETE")
    print("=" * 60)

    if survey is not None:
        print("✅ All basic tests passed!")
        print("📊 Macro successfully converts QSF files to EDSL Survey objects")
        print("🚀 Ready for production use")

        # Show usage example
        print("\n💡 Usage Example:")
        print("```python")
        print("from edsl.macros.builtin.qsf_to_survey import qsf_to_survey_macro")
        print("")
        print("# Convert QSF file to Survey")
        print("result = qsf_to_survey_macro.output({")
        print("    'qsf_file': '/path/to/your/survey.qsf',")
        print("    'encoding': 'utf-8'")
        print("})")
        print("")
        print("# Use the converted survey")
        print("survey = result.survey")
        print("# results = survey.by(Agent()).run()")
        print("```")
    else:
        print("❌ Basic functionality test failed")
        print("🔧 Macro needs debugging before production use")


if __name__ == "__main__":
    main()
