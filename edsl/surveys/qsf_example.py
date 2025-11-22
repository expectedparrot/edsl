"""
Example of how to use Survey.from_qsf() to convert Qualtrics QSF files to EDSL surveys.

This example shows how to:
1. Load a QSF file using Survey.from_qsf()
2. Inspect the converted survey
3. Run the survey with an agent (optional)
"""

import json
import tempfile
from pathlib import Path


def create_example_qsf():
    """
    Create an example QSF file that demonstrates different question types.

    This creates a QSF with:
    - Multiple choice question (single answer)
    - Text input question
    - Multiple choice question (multiple answers - checkbox)
    - Yes/No question
    """
    sample_qsf = {
        "SurveyEntry": {
            "SurveyID": "SV_example123",
            "SurveyName": "Customer Feedback Survey",
            "SurveyDescription": "A sample customer feedback survey",
            "SurveyLanguage": "EN"
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
                        "5": {"Display": "Very Satisfied"}
                    },
                    "ChoiceOrder": ["1", "2", "3", "4", "5"]
                }
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
                    "QuestionText": "Please tell us what we could improve:"
                }
            },
            # Multiple choice (checkbox) question
            {
                "Element": "SQ",
                "PrimaryAttribute": "QID3",
                "Payload": {
                    "QuestionID": "QID3",
                    "QuestionType": "MC",
                    "Selector": "MAVR",
                    "DataExportTag": "features_used",
                    "QuestionText": "Which features do you use regularly? (Select all that apply)",
                    "Choices": {
                        "1": {"Display": "Online Chat"},
                        "2": {"Display": "Phone Support"},
                        "3": {"Display": "Email Support"},
                        "4": {"Display": "Knowledge Base"},
                        "5": {"Display": "Video Tutorials"}
                    },
                    "ChoiceOrder": ["1", "2", "3", "4", "5"]
                }
            },
            # Yes/No question
            {
                "Element": "SQ",
                "PrimaryAttribute": "QID4",
                "Payload": {
                    "QuestionID": "QID4",
                    "QuestionType": "MC",
                    "Selector": "SAVR",
                    "DataExportTag": "recommend",
                    "QuestionText": "Would you recommend our service to a friend?",
                    "Choices": {
                        "1": {"Display": "Yes"},
                        "2": {"Display": "No"}
                    },
                    "ChoiceOrder": ["1", "2"]
                }
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
                            {"Type": "Question", "QuestionID": "QID3"},
                            {"Type": "Question", "QuestionID": "QID4"}
                        ]
                    }
                ]
            },
            # Flow definition
            {
                "Element": "FL",
                "Payload": {
                    "Type": "Root",
                    "Flow": [
                        {
                            "Type": "Block",
                            "ID": "BL_main"
                        }
                    ]
                }
            }
        ]
    }
    return sample_qsf


def example_basic_usage():
    """Basic example of QSF conversion."""
    print("=== Basic QSF Conversion Example ===")

    # Create example QSF file
    sample_qsf = create_example_qsf()

    # Save to temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.qsf', delete=False) as f:
        json.dump(sample_qsf, f, indent=2)
        qsf_path = f.name

    try:
        # Convert QSF to EDSL Survey
        from edsl import Survey

        print(f"Loading QSF file: {qsf_path}")
        survey = Survey.from_qsf(qsf_path)

        print("✅ Conversion successful!")
        print(f"Survey questions: {len([q for q in survey.questions if hasattr(q, 'question_name')])}")

        # Display question details
        print("\nConverted Questions:")
        for i, question in enumerate(survey.questions):
            if hasattr(question, 'question_name'):
                q_type = type(question).__name__
                print(f"  {i+1}. {question.question_name} ({q_type})")
                print(f"     Text: {question.question_text}")
                if hasattr(question, 'question_options') and question.question_options:
                    print(f"     Options: {question.question_options}")
                print()

        return survey

    except Exception as e:
        print(f"❌ Error: {e}")
        return None

    finally:
        # Clean up
        Path(qsf_path).unlink()


def example_with_agent():
    """Example of running the converted survey with an agent."""
    print("=== Running Survey with Agent ===")

    try:
        # Get the converted survey
        survey = example_basic_usage()

        if survey is None:
            print("Cannot run agent example - conversion failed")
            return

        # Uncomment the following to run with an actual agent
        # (requires proper EDSL setup with API keys)

        # from edsl import Agent
        #
        # # Create an agent with some traits
        # agent = Agent(traits={"name": "Survey Respondent"})
        #
        # # Run the survey
        # print("Running survey with agent...")
        # results = survey.by(agent).run()
        #
        # # Display results
        # print("Survey Results:")
        # for result in results:
        #     print(result.select("question_name", "answer"))

        print("Agent execution example (commented out)")
        print("To run with an actual agent:")
        print("1. Uncomment the agent code above")
        print("2. Ensure you have EDSL properly configured with API keys")
        print("3. Run this script again")

    except Exception as e:
        print(f"❌ Error: {e}")


def example_survey_customization():
    """Example of customizing the converted survey."""
    print("\n=== Survey Customization Example ===")

    try:
        # Get the converted survey
        survey = example_basic_usage()

        if survey is None:
            print("Cannot customize - conversion failed")
            return

        # Add some skip logic
        print("Adding skip logic...")

        # Example: Skip feedback question if satisfaction is "Very Satisfied"
        # survey.add_rule(
        #     "satisfaction",
        #     "{{ satisfaction.answer == 'Very Satisfied' }}",
        #     "features_used"
        # )

        # Add question groups
        print("Setting question groups...")
        survey.question_groups = {
            "satisfaction_section": (0, 1),  # satisfaction and feedback questions
            "usage_section": (2, 3)          # features and recommendation questions
        }

        # Add questions to randomize
        print("Setting randomization...")
        survey.questions_to_randomize = ["features_used"]

        print("✅ Survey customization complete!")
        print(f"Question groups: {survey.question_groups}")
        print(f"Questions to randomize: {survey.questions_to_randomize}")

        # Show the survey can be serialized
        survey_dict = survey.to_dict()
        print(f"Survey serialized successfully ({len(survey_dict)} keys)")

    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    print("QSF to EDSL Conversion Examples")
    print("=" * 50)

    # Run examples
    example_basic_usage()
    example_with_agent()
    example_survey_customization()

    print("\n" + "=" * 50)
    print("Examples completed!")
    print("\nTo use with your own QSF files:")
    print("1. Save your QSF file from Qualtrics")
    print("2. Use: survey = Survey.from_qsf('your_file.qsf')")
    print("3. Customize the survey as needed")
    print("4. Run with an agent: results = survey.by(agent).run()")