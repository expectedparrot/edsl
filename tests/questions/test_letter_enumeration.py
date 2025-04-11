"""Tests for the letter enumeration feature in QuestionMultipleChoice."""

import pytest
from edsl.questions import QuestionMultipleChoice


def test_letter_enumeration_initialization():
    """Test that QuestionMultipleChoice can be initialized with letter enumeration."""
    q = QuestionMultipleChoice(
        question_name="test",
        question_text="Which option do you prefer?",
        question_options=["Option 1", "Option 2", "Option 3"],
        enumeration_style="letter"
    )
    assert q.enumeration_style == "letter"


def test_letter_enumeration_with_use_code():
    """Test that letter enumeration works correctly with use_code=True."""
    q = QuestionMultipleChoice(
        question_name="test",
        question_text="Which option do you prefer?",
        question_options=["Option 1", "Option 2", "Option 3"],
        enumeration_style="letter",
        use_code=True
    )
    
    # Check that the response model allows for letter codes
    response_model = q.create_response_model()
    valid_letters = ['A', 'B', 'C']
    
    # Validate the model accepts letter codes
    for letter in valid_letters:
        response = response_model(answer=letter)
        assert response.answer == letter
    
    # Translate letter codes to actual answers
    assert q._translate_answer_code_to_answer('A', {}) == "Option 1"
    assert q._translate_answer_code_to_answer('B', {}) == "Option 2"
    assert q._translate_answer_code_to_answer('C', {}) == "Option 3"


def test_letter_case_insensitivity():
    """Test that letter enumeration is case-insensitive."""
    q = QuestionMultipleChoice(
        question_name="test",
        question_text="Which option do you prefer?",
        question_options=["Option 1", "Option 2", "Option 3"],
        enumeration_style="letter",
        use_code=True
    )
    
    # Both uppercase and lowercase should work
    assert q._translate_answer_code_to_answer('A', {}) == "Option 1"
    assert q._translate_answer_code_to_answer('a', {}) == "Option 1"


def test_invalid_letter_code():
    """Test that invalid letter codes raise appropriate exceptions."""
    q = QuestionMultipleChoice(
        question_name="test",
        question_text="Which option do you prefer?",
        question_options=["Option 1", "Option 2"],
        enumeration_style="letter",
        use_code=True
    )
    
    # Letter code out of range
    with pytest.raises(Exception):
        q._translate_answer_code_to_answer('C', {})
    
    # Invalid letter code
    with pytest.raises(Exception):
        q._translate_answer_code_to_answer('!', {})


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])