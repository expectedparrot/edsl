#!/usr/bin/env python3
"""
Test script for n parameter implementation in EDSL.

This tests John Horton's approach: passing n to run() method
rather than to Model initialization.
"""

from edsl import Model, QuestionFreeText, Survey
from edsl.agents import Agent


def test_n_parameter_in_run():
    """Test that run(n=5) properly uses native API support."""
    
    # Create a simple question
    question = QuestionFreeText(
        question_name="number",
        question_text="Pick a random number between 1 and 100. Reply with just the number:"
    )
    
    # Create a survey from the question
    survey = question.to_survey()
    
    # Test with OpenAI model (supports n≤128)
    print("Testing OpenAI with run(n=5)...")
    model = Model("gpt-4o-mini", service_name="openai")
    
    # Run with n=5 - should use native n parameter
    results = survey.by(model).run(n=5)
    
    print(f"Results count: {len(results.to_list())}")
    print(f"Expected: 5")
    
    # Check if we got 5 different responses
    responses = [r.get("number") for r in results.to_list()]
    print(f"Responses: {responses}")
    
    # Test unique responses
    unique_responses = len(set(responses))
    print(f"Unique responses: {unique_responses}")
    
    if len(responses) == 5:
        print("✅ PASS: Got 5 responses using run(n=5)")
    else:
        print("❌ FAIL: Did not get 5 responses")
    
    return results


def test_google_candidatecount():
    """Test Google's candidateCount parameter through run()."""
    
    question = QuestionFreeText(
        question_name="color",
        question_text="Name a random color. Reply with just the color name:"
    )
    
    survey = question.to_survey()
    
    print("\nTesting Google Gemini with run(n=4)...")
    model = Model("gemini-2.5-flash", service_name="google")
    
    # Run with n=4 - should use candidateCount
    results = survey.by(model).run(n=4)
    
    responses = [r.get("color") for r in results.to_list()]
    print(f"Responses: {responses}")
    print(f"Count: {len(responses)}")
    
    if len(responses) == 4:
        print("✅ PASS: Got 4 responses using run(n=4) with Gemini")
    else:
        print("❌ FAIL: Did not get 4 responses")
    
    return results


def test_batching_large_n():
    """Test batching when n exceeds provider limits."""
    
    question = QuestionFreeText(
        question_name="animal",
        question_text="Name an animal. Reply with just the animal name:"
    )
    
    survey = question.to_survey()
    
    print("\nTesting OpenAI with run(n=150) - should batch as 128 + 22...")
    model = Model("gpt-4o-mini", service_name="openai")
    
    # Run with n=150 - should batch into 128 + 22
    results = survey.by(model).run(n=150)
    
    print(f"Total results: {len(results.to_list())}")
    
    if len(results.to_list()) == 150:
        print("✅ PASS: Successfully batched large n value")
    else:
        print("❌ FAIL: Batching did not work correctly")
    
    return results


if __name__ == "__main__":
    print("=" * 60)
    print("Testing n Parameter Implementation (John Horton's Approach)")
    print("=" * 60)
    
    # Run tests
    try:
        # Test basic n parameter
        test_n_parameter_in_run()
        
        # Test Google candidateCount
        # test_google_candidatecount()  # Uncomment if Google API key is available
        
        # Test batching for large n
        # test_batching_large_n()  # Uncomment for full test
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60)