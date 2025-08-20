"""
Test case-insensitive validation for multiple choice questions.

This test validates the fix for issue #2008 where capitalized versions
of valid options should be accepted (e.g., "Grapefruit" vs "grapefruit").
"""

import pytest
from edsl.questions import QuestionMultipleChoice


class TestMultipleChoiceCaseInsensitive:
    """Test case-insensitive validation for multiple choice questions."""
    
    def test_capitalized_options_validate_correctly(self):
        """Test that capitalized versions of options are accepted."""
        q = QuestionMultipleChoice(
            question_name="fruit_choice",
            question_text="What is your favorite fruit?",
            question_options=["apple", "banana", "grapefruit", "orange"]
        )
        
        validator = q.response_validator
        
        # Test various capitalization patterns
        test_cases = [
            ("apple", "apple"),        # exact match
            ("Apple", "apple"),        # capitalize first
            ("APPLE", "apple"),        # all uppercase  
            ("aPpLe", "apple"),        # mixed case
            ("grapefruit", "grapefruit"),  # exact match
            ("Grapefruit", "grapefruit"),  # issue #2008 example
            ("GRAPEFRUIT", "grapefruit"),  # all uppercase
            ("GrapeFruit", "grapefruit"),  # camel case
        ]
        
        for input_answer, expected_answer in test_cases:
            response = {"answer": input_answer}
            # Reset validator state for clean test
            validator.fixes_tried = 0
            result = validator.validate(response)
            
            assert result["answer"] == expected_answer, \
                f"Expected '{input_answer}' to validate as '{expected_answer}', got '{result['answer']}'"
    
    def test_mixed_case_options_validate_correctly(self):
        """Test case-insensitive validation with mixed-case option lists."""
        q = QuestionMultipleChoice(
            question_name="rating",
            question_text="How would you rate this?",
            question_options=["Very Good", "Good", "OK", "Bad", "Very Bad"]
        )
        
        validator = q.response_validator
        
        # Test various input cases against mixed-case options
        test_cases = [
            ("Very Good", "Very Good"),    # exact match
            ("very good", "Very Good"),    # lowercase input
            ("VERY GOOD", "Very Good"),    # uppercase input
            ("Very GOOD", "Very Good"),    # mixed case input
            ("OK", "OK"),                  # exact match
            ("ok", "OK"),                  # lowercase
            ("Ok", "OK"),                  # title case
            ("bad", "Bad"),                # lowercase
            ("BAD", "Bad"),                # uppercase
        ]
        
        for input_answer, expected_answer in test_cases:
            response = {"answer": input_answer}
            # Reset validator state for clean test
            validator.fixes_tried = 0
            result = validator.validate(response)
            
            assert result["answer"] == expected_answer, \
                f"Expected '{input_answer}' to validate as '{expected_answer}', got '{result['answer']}'"
    
    def test_case_insensitive_substring_matching(self):
        """Test case-insensitive matching works in longer text responses."""
        q = QuestionMultipleChoice(
            question_name="choice",
            question_text="Choose an option:",
            question_options=["Red Car", "Blue Car", "Green Car"]
        )
        
        validator = q.response_validator
        
        # Test responses that contain the option in different cases
        test_cases = [
            ("I choose Red Car", "Red Car"),
            ("I choose red car", "Red Car"),
            ("I choose RED CAR", "Red Car"),
            ("My answer is Blue Car", "Blue Car"),
            ("My answer is blue car", "Blue Car"),
            ("My answer is BLUE CAR", "Blue Car"),
        ]
        
        for input_response, expected_answer in test_cases:
            response = {"answer": input_response}
            # Reset validator state for clean test
            validator.fixes_tried = 0
            result = validator.validate(response)
            
            assert result["answer"] == expected_answer, \
                f"Expected '{input_response}' to validate as '{expected_answer}', got '{result['answer']}'"
    
    def test_fix_method_handles_case_differences(self):
        """Test that the fix method specifically handles case differences."""
        q = QuestionMultipleChoice(
            question_name="test",
            question_text="Choose:",
            question_options=["apple", "banana", "cherry"]
        )
        
        validator = q.response_validator
        
        # Test fix method directly
        test_cases = [
            ("Apple", "apple"),
            ("BANANA", "banana"), 
            ("CheRRy", "cherry"),
        ]
        
        for input_answer, expected_answer in test_cases:
            response = {"answer": input_answer}
            fixed_response = validator.fix(response)
            
            assert fixed_response["answer"] == expected_answer, \
                f"Expected fix to change '{input_answer}' to '{expected_answer}', got '{fixed_response['answer']}'"
            
            # Ensure the fixed response validates
            validator.response_model.model_validate(fixed_response)
    
    def test_invalid_answers_still_rejected(self):
        """Test that truly invalid answers are still rejected."""
        q = QuestionMultipleChoice(
            question_name="test",
            question_text="Choose:",
            question_options=["apple", "banana", "cherry"]
        )
        
        validator = q.response_validator
        
        # These should still fail validation
        invalid_cases = ["grape", "MANGO", "Invalid Option", "", None]
        
        for invalid_answer in invalid_cases:
            response = {"answer": invalid_answer}
            
            with pytest.raises(Exception):
                validator.validate(response)
    
    def test_github_issue_2008_specific_case(self):
        """Test the specific case mentioned in GitHub issue #2008."""
        # Reproduce the exact scenario from the issue
        q = QuestionMultipleChoice(
            question_name="fruit",
            question_text="What fruit do you prefer?",
            question_options=["apple", "banana", "grapefruit", "orange"]  
        )
        
        validator = q.response_validator
        
        # The issue: gemini-1.5-flash returned "Grapefruit" instead of "grapefruit"
        response = {"answer": "Grapefruit"}
        result = validator.validate(response)
        
        # Should validate successfully and return the correct lowercase version
        assert result["answer"] == "grapefruit"
        assert "comment" in result
        assert "generated_tokens" in result