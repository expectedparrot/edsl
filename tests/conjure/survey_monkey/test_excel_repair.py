#!/usr/bin/env python3
"""Test script for Excel date repair functionality.

This script demonstrates how the Excel date repair functionality works
by testing the ExcelDateRepairer class directly with sample data.
"""

import os
import sys
from typing import List

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from excel_date_repairer import ExcelDateRepairer


def test_basic_repair():
    """Test basic Excel date repair functionality."""
    print("🔧 Testing Excel Date Repair Functionality")
    print("=" * 60)

    # Initialize the repairer
    try:
        repairer = ExcelDateRepairer(verbose=True)
        print("✅ ExcelDateRepairer initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize ExcelDateRepairer: {e}")
        print("Note: This requires OPENAI_API_KEY environment variable")
        return False

    # Test data that mimics Excel-mangled survey options
    test_cases = [
        {
            "question": "How many projects per week?",
            "options": ["More than 10", "5-Mar", "2-Jan", "10-Jun", "0"]
        },
        {
            "question": "Age range",
            "options": ["18-25", "5-Mar", "10-Jun", "15-Nov", "65+"]
        },
        {
            "question": "Experience level",
            "options": ["Beginner", "Intermediate", "Advanced", "Expert"]
        },
        {
            "question": "Years of experience",
            "options": ["1-Jan", "3-May", "6-Oct", "More than 10"]
        }
    ]

    print(f"\n📋 Testing {len(test_cases)} question scenarios...")
    print("-" * 60)

    all_repairs = {}

    for i, test_case in enumerate(test_cases, 1):
        question = test_case["question"]
        options = test_case["options"]

        print(f"\n{i}. Question: {question}")
        print(f"   Original options: {options}")

        try:
            # Test the repair functionality
            repair_result = repairer.repair_question_options(question, options)

            print(f"   Repaired options: {repair_result.repaired_options}")

            if repair_result.any_repairs_applied:
                print(f"   ✅ Applied {len(repair_result.repairs_made)} repairs:")
                for repair in repair_result.repairs_made:
                    print(f"      '{repair.original}' → '{repair.repaired}' "
                          f"(confidence: {repair.confidence:.2f}, {repair.repair_type})")
                    print(f"      Reason: {repair.explanation}")
                    # Track for overall summary
                    all_repairs[repair.original] = repair.repaired
            else:
                print("   ℹ️  No repairs needed")

        except Exception as e:
            print(f"   ❌ Error during repair: {e}")

    # Print overall summary
    print("\n" + "=" * 60)
    print(f"📊 REPAIR SUMMARY")
    print("=" * 60)

    if all_repairs:
        print(f"Total repairs applied: {len(all_repairs)}")
        for original, repaired in all_repairs.items():
            print(f"  '{original}' → '{repaired}'")

        print("\nThese repairs would be applied to:")
        print("• Survey question options during import")
        print("• Individual respondent answers in the data")
    else:
        print("No Excel date formatting issues detected in test data")

    print("\n✨ Test completed!")
    return True


def test_response_mapping():
    """Test how response values would be mapped using repair results."""
    print("\n🔄 Testing Response Value Mapping")
    print("=" * 60)

    # Simulate repair mapping that would be built during import
    repair_mapping = {
        "5-Mar": "3-5",
        "10-Jun": "6-10",
        "2-Jan": "1-2",
        "15-Nov": "11-15"
    }

    # Simulate respondent answers that need to be repaired
    sample_responses = [
        {"question_1": "5-Mar", "question_2": "Expert"},
        {"question_1": "10-Jun", "question_2": "Advanced"},
        {"question_1": "More than 10", "question_2": "Beginner"},
        {"question_1": "2-Jan", "question_2": "Intermediate"}
    ]

    print("Repair mapping:", repair_mapping)
    print("\nOriginal responses:")
    for i, response in enumerate(sample_responses, 1):
        print(f"  Respondent {i}: {response}")

    print("\nRepaired responses:")
    for i, response in enumerate(sample_responses, 1):
        repaired_response = {}
        for key, value in response.items():
            # Apply repair mapping (same logic as in _build_response_records)
            repaired_value = repair_mapping.get(value, value)
            repaired_response[key] = repaired_value
        print(f"  Respondent {i}: {repaired_response}")

    print("\n✅ Response mapping test completed!")


if __name__ == "__main__":
    print("Excel Date Repair Test Suite")
    print("This script tests the LLM-based repair functionality")
    print("Requires OPENAI_API_KEY environment variable to be set")
    print()

    # Check if API key is available
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Warning: OPENAI_API_KEY not found in environment")
        print("The LLM repair test will likely fail, but response mapping test will work")
        print()

    # Run tests
    success = test_basic_repair()
    test_response_mapping()

    if success:
        print("\n🎉 All tests completed successfully!")
        print("\nTo use this in your SurveyMonkey import:")
        print("  importer = ImportSurveyMonkey('survey.csv', repair_excel_dates=True)")
        print("  importer.print_excel_date_repairs()")
    else:
        print("\n⚠️  Some tests failed - check your environment setup")