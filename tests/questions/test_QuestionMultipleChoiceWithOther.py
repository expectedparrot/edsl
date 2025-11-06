"""Tests for the QuestionMultipleChoiceWithOther class."""

from edsl.questions import QuestionMultipleChoiceWithOther


def test_question_multiple_choice_with_other_basics():
    """Test basic functionality of QuestionMultipleChoiceWithOther."""
    q = QuestionMultipleChoiceWithOther(
        question_name="test_question",
        question_text="Select a color:",
        question_options=["Red", "Green", "Blue"],
    )
    
    # Check that the question has the correct attributes
    assert q.question_name == "test_question"
    assert q.question_text == "Select a color:"
    assert q.question_options == ["Red", "Green", "Blue"]
    assert q.other_option_text == "Other"
    
    # Check that the validator has the correct attributes
    validator = q.response_validator
    assert validator.__class__.__name__ == "MultipleChoiceWithOtherResponseValidator"
    assert "Other" in validator.question_options


def test_post_process_result_other_format():
    """Test the post_process_result method with 'Other: X' format."""
    # Create the question
    q = QuestionMultipleChoiceWithOther(
        question_name="capital",
        question_text="What is the capital of France?",
        question_options=["London", "Berlin", "Madrid"],
    )
    
    # Create a result with 'Other: Paris' format
    result = [{
        'answer': {'capital': 'Other: Paris'},
        'other_text': {}
    }]
    
    # Apply post-processing
    processed = q.post_process_result(result)
    
    # Check the results
    assert processed[0]['answer']['capital'] == "Other"
    assert processed[0]['other_text']['capital_other_text'] == "Paris"


def test_validator_direct():
    """Test the validator directly with 'Other: X' format."""
    # Create the question
    q = QuestionMultipleChoiceWithOther(
        question_name="capital",
        question_text="What is the capital of France?",
        question_options=["London", "Berlin", "Madrid"],
    )
    
    # Get the validator
    validator = q.response_validator
    
    # Test with 'Other: X' format
    response = {"answer": "Other: Paris"}
    validated = validator.validate(response, verbose=True)
    
    # Check that we correctly parsed the 'Other: X' format
    assert validated["answer"] == "Other"
    assert "other_text" in validated
    assert validated["other_text"] == "Paris"


def test_validator_fix_method():
    """Test the validator's fix method with 'Other: X' format."""
    # Create the question
    q = QuestionMultipleChoiceWithOther(
        question_name="capital",
        question_text="What is the capital of France?",
        question_options=["London", "Berlin", "Madrid"],
    )
    
    # Get the validator
    validator = q.response_validator
    
    # Test with 'Other: X' format
    response = {"answer": "Other: Paris"}
    fixed = validator.fix(response, verbose=True)
    
    # Check that we correctly fixed the 'Other: X' format
    assert fixed["answer"] == "Other"
    assert "other_text" in fixed
    assert fixed["other_text"] == "Paris"


def test_other_option_text_custom():
    """Test with custom other_option_text."""
    # Create the question with custom other_option_text
    q = QuestionMultipleChoiceWithOther(
        question_name="capital",
        question_text="What is the capital of France?",
        question_options=["London", "Berlin", "Madrid"],
        other_option_text="Something else"
    )
    
    # Create a result with 'Something else: Paris' format
    result = [{
        'answer': {'capital': 'Something else: Paris'},
        'other_text': {}
    }]
    
    # Apply post-processing - should still work because we use hardcoded "Other"
    processed = q.post_process_result(result)
    
    # It should match the standard "Other" regardless of other_option_text
    assert processed[0]['answer']['capital'] == "Other"
    assert processed[0]['other_text']['capital_other_text'] == "Paris"