#!/usr/bin/env python3
"""Test script for semantic option ordering functionality.

This script demonstrates how the LLM-based semantic ordering works by testing
the OptionSemanticOrderer class directly with various question types.
"""

import os
import sys
from typing import List

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from option_semantic_orderer import OptionSemanticOrderer


def test_semantic_ordering():
    """Test semantic ordering functionality with various question types."""
    print("🎯 Testing Semantic Option Ordering Functionality")
    print("=" * 65)

    # Initialize the orderer
    try:
        orderer = OptionSemanticOrderer(verbose=True)
        print("✅ OptionSemanticOrderer initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize OptionSemanticOrderer: {e}")
        print("Note: This requires OPENAI_API_KEY environment variable")
        return False

    # Test cases with different types of semantic ordering needs
    test_cases = [
        {
            "question": "What is the size of your company?",
            "options": ["Large (500+)", "Small (1-49)", "Medium (50-499)", "Startup (1-10)"],
            "expected_pattern": "size_ascending"
        },
        {
            "question": "What is your experience level with this software?",
            "options": ["Expert", "Beginner", "Advanced", "Intermediate"],
            "expected_pattern": "experience_level"
        },
        {
            "question": "How often do you use this feature?",
            "options": ["Always", "Never", "Sometimes", "Rarely", "Often"],
            "expected_pattern": "frequency"
        },
        {
            "question": "What is your age range?",
            "options": ["65+", "25-34", "18-24", "45-54", "35-44", "55-64"],
            "expected_pattern": "age_range"
        },
        {
            "question": "How satisfied are you with our service?",
            "options": ["Very satisfied", "Dissatisfied", "Neutral", "Satisfied", "Very dissatisfied"],
            "expected_pattern": "satisfaction_scale"
        },
        {
            "question": "Which department do you work in?",
            "options": ["Marketing", "Engineering", "Sales", "HR", "Finance"],
            "expected_pattern": "no_ordering_needed"
        },
        {
            "question": "For approximately how many projects do you perform takeoff on per week?",
            "options": ["More than 10", "5-Mar", "2-Jan", "10-Jun", "0"],  # Excel-mangled data
            "expected_pattern": "quantity_ascending"
        }
    ]

    print(f"\n📋 Testing {len(test_cases)} question scenarios...")
    print("-" * 65)

    successful_orderings = 0
    total_reorderings = 0

    for i, test_case in enumerate(test_cases, 1):
        question = test_case["question"]
        options = test_case["options"]
        expected = test_case["expected_pattern"]

        print(f"\n{i}. Question: {question}")
        print(f"   Original options: {options}")

        try:
            # Test the ordering functionality
            ordering_result = orderer.order_question_options(question, f"test_q_{i}", options)

            print(f"   Ordered options: {ordering_result.ordering_details.semantic_order}")
            print(f"   Ordering type: {ordering_result.ordering_details.ordering_type}")
            print(f"   Confidence: {ordering_result.ordering_details.confidence:.2f}")

            if ordering_result.ordering_details.reordering_applied:
                total_reorderings += 1
                print(f"   ✅ Reordering applied: {ordering_result.ordering_details.explanation}")

                # Check if options actually changed
                if ordering_result.ordering_details.original_order != ordering_result.ordering_details.semantic_order:
                    successful_orderings += 1
                else:
                    print(f"   ⚠️  Options unchanged despite reordering_applied=True")
            else:
                print(f"   ℹ️  No reordering needed: {ordering_result.ordering_details.explanation}")

            print(f"   Category: {ordering_result.question_category}")

        except Exception as e:
            print(f"   ❌ Error during ordering: {e}")

    # Print overall summary
    print("\n" + "=" * 65)
    print(f"📊 ORDERING SUMMARY")
    print("=" * 65)

    print(f"Questions processed: {len(test_cases)}")
    print(f"Reorderings applied: {total_reorderings}")
    print(f"Successful reorderings: {successful_orderings}")

    if total_reorderings > 0:
        print(f"\n✨ Examples of semantic improvements:")
        print(f"• Company sizes: Small → Medium → Large")
        print(f"• Experience: Beginner → Intermediate → Advanced → Expert")
        print(f"• Frequency: Never → Rarely → Sometimes → Often → Always")
        print(f"• Age ranges: Youngest to oldest in chronological order")
        print(f"• Satisfaction: Most negative to most positive")
    else:
        print(f"\n⚠️  No reorderings were applied - check LLM connectivity")

    print(f"\n🎯 Test completed!")
    return successful_orderings > 0


def test_multiple_questions():
    """Test the batch processing functionality."""
    print("\n🔄 Testing Multiple Questions Processing")
    print("=" * 65)

    try:
        orderer = OptionSemanticOrderer(verbose=False)  # Less verbose for batch test
    except Exception as e:
        print(f"❌ Failed to initialize orderer: {e}")
        return False

    # Sample questions for batch processing
    questions_data = [
        {
            'question_text': 'What is your income range?',
            'question_identifier': 'income',
            'options': ['$100k+', '$25k-$50k', '$50k-$75k', 'Under $25k', '$75k-$100k']
        },
        {
            'question_text': 'How many employees work at your company?',
            'question_identifier': 'employees',
            'options': ['1000+', '1-10', '51-250', '11-50', '251-1000']
        },
        {
            'question_text': 'Which social media platform do you use most?',
            'question_identifier': 'social_media',
            'options': ['Instagram', 'Twitter', 'Facebook', 'LinkedIn', 'TikTok']
        }
    ]

    try:
        batch_result = orderer.order_multiple_questions(questions_data)

        print(f"📊 Processed {len(batch_result.questions)} questions")
        print(f"🔧 Applied {batch_result.total_reorderings} reorderings")
        print(f"🎯 High confidence reorderings: {batch_result.high_confidence_reorderings}")
        print(f"\n📝 Summary: {batch_result.summary}")

        print(f"\n📋 Detailed Results:")
        for q_result in batch_result.questions:
            if q_result.ordering_details.reordering_applied:
                print(f"\n• {q_result.question_text}")
                print(f"  Type: {q_result.ordering_details.ordering_type}")
                print(f"  Before: {q_result.ordering_details.original_order}")
                print(f"  After:  {q_result.ordering_details.semantic_order}")

        return True

    except Exception as e:
        print(f"❌ Batch processing failed: {e}")
        return False


def show_integration_example():
    """Show how to use semantic ordering in the full import pipeline."""
    print("\n🏗️  Integration with ImportSurveyMonkey")
    print("=" * 65)

    print("To use semantic ordering in your SurveyMonkey import:")
    print()

    print("# Basic usage (both features enabled by default):")
    print("importer = ImportSurveyMonkey('survey.csv')")
    print("survey = importer.survey  # Options repaired and ordered")
    print("importer.print_excel_date_repairs()         # See repairs")
    print("importer.print_semantic_ordering_changes()  # See reorderings")
    print()

    print("# Access changes programmatically:")
    print("repairs = importer.get_excel_date_repairs()")
    print("orderings = importer.get_semantic_ordering_changes()")
    print()

    print("# Disable specific features if needed:")
    print("importer = ImportSurveyMonkey('survey.csv',")
    print("                             repair_excel_dates=True,")
    print("                             order_options_semantically=False)")
    print()

    print("✨ Both features work together:")
    print("1️⃣  Excel dates are repaired first (5-Mar → 3-5)")
    print("2️⃣  Then options are semantically ordered (Small → Medium → Large)")
    print("3️⃣  Response values are mapped consistently")


if __name__ == "__main__":
    print("Semantic Option Ordering Test Suite")
    print("This script tests the LLM-based semantic ordering functionality")
    print("Requires OPENAI_API_KEY environment variable to be set")
    print()

    # Check if API key is available
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Warning: OPENAI_API_KEY not found in environment")
        print("The semantic ordering tests will likely fail")
        print("Set it with: export OPENAI_API_KEY='your-key-here'")
        print()

    # Run tests
    success1 = test_semantic_ordering()
    success2 = test_multiple_questions()
    show_integration_example()

    if success1 and success2:
        print("\n🎉 All tests completed successfully!")
        print("\nSemantic ordering will help organize your survey options")
        print("for better readability and respondent experience!")
    else:
        print("\n⚠️  Some tests failed - check your environment setup")
        print("Make sure OPENAI_API_KEY is set and you have internet access")