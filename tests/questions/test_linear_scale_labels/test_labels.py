"""
Test label handling in linear scale questions.
This tests the fix for issue #1921 where a model may return a label instead of an integer.
"""

from edsl.questions import QuestionLinearScale


def test_label_to_option_conversion():
    """Test that a label response is converted to the correct option value."""
    q = QuestionLinearScale(
        question_name="feeling",
        question_text="How do you feel about this product?",
        question_options=[1, 2, 3, 4, 5],
        option_labels={1: "Hate it", 3: "Neutral", 5: "Love it"}
    )
    
    # Enable verbose for debugging
    verbose = True
    
    # Test label matching exactly
    test_answer = {"answer": "Love it", "comment": "It's amazing!"}
    fixed_answer = q.response_validator.fix(test_answer, verbose=verbose)
    assert fixed_answer["answer"] == 5
    
    # Test partial label matching
    test_answer = {"answer": "I love", "comment": "Great product"}
    fixed_answer = q.response_validator.fix(test_answer, verbose=verbose)
    assert fixed_answer["answer"] == 5
    
    # Test case insensitivity
    test_answer = {"answer": "HATE IT", "comment": "Terrible product"}
    fixed_answer = q.response_validator.fix(test_answer, verbose=verbose)
    assert fixed_answer["answer"] == 1
    
    # Test with surrounding text
    test_answer = {"answer": "I would say I'm neutral about it", "comment": "It's okay"}
    fixed_answer = q.response_validator.fix(test_answer, verbose=verbose)
    assert fixed_answer["answer"] == 3


def test_validator_preserves_valid_answers():
    """Test that valid integer answers are preserved."""
    q = QuestionLinearScale(
        question_name="rating",
        question_text="Rate this product from 1 to 5",
        question_options=[1, 2, 3, 4, 5],
        option_labels={1: "Poor", 5: "Excellent"}
    )
    
    # Enable verbose for debugging
    verbose = True
    
    # Test with a valid integer answer
    valid_answer = {"answer": 4, "comment": "Good product"}
    fixed_answer = q.response_validator.fix(valid_answer, verbose=verbose)
    assert fixed_answer["answer"] == 4
    
    # Test with a valid integer as string
    valid_string_answer = {"answer": "2", "comment": "Not great"}
    fixed_answer = q.response_validator.fix(valid_string_answer, verbose=verbose)
    # The standard MultipleChoiceResponseValidator should convert this to integer 2
    assert fixed_answer["answer"] == 2


def test_fallback_behavior():
    """Test that the validator falls back to parent class behavior for non-matching labels."""
    q = QuestionLinearScale(
        question_name="satisfaction",
        question_text="How satisfied are you?",
        question_options=[1, 2, 3, 4, 5],
        option_labels={1: "Very dissatisfied", 5: "Very satisfied"}
    )
    
    # Enable verbose for debugging
    verbose = True
    
    # Test with a non-matching label
    non_matching = {"answer": "Somewhat okay", "comment": "It's fine"}
    # The fix should try to find a match but ultimately leave it unchanged
    # since there's no close match to the option labels
    fixed_answer = q.response_validator.fix(non_matching, verbose=verbose)
    assert fixed_answer == non_matching