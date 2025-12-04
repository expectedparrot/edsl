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

    # Check that we keep the full answer string (new behavior)
    assert validated["answer"] == "Other: Paris"


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

    # Check that we keep the full answer string (new behavior)
    assert fixed["answer"] == "Other: Paris"


def test_other_option_text_custom():
    """Test with custom other_option_text."""
    # Create the question with custom other_option_text
    q = QuestionMultipleChoiceWithOther(
        question_name="capital",
        question_text="What is the capital of France?",
        question_options=["London", "Berlin", "Madrid"],
        other_option_text="Something else",
    )

    # Get the validator
    validator = q.response_validator

    # Test with 'Something else: Paris' format
    response = {"answer": "Something else: Paris"}
    validated = validator.validate(response, verbose=True)

    # Check that we keep the full answer string (new behavior)
    assert validated["answer"] == "Something else: Paris"


def test_validator_regular_answer():
    """Test that regular (non-other) answers are validated correctly."""
    # Create the question
    q = QuestionMultipleChoiceWithOther(
        question_name="color",
        question_text="What is your favorite color?",
        question_options=["Red", "Green", "Blue"],
    )

    # Get the validator
    validator = q.response_validator

    # Test with a valid regular answer
    response = {"answer": "Red"}
    validated = validator.validate(response, verbose=False)

    # Check that the answer is validated correctly
    assert validated["answer"] == "Red"

    # Test with another valid regular answer
    response = {"answer": "Green"}
    validated = validator.validate(response, verbose=False)
    assert validated["answer"] == "Green"

    # Test with "Blue"
    response = {"answer": "Blue"}
    validated = validator.validate(response, verbose=False)
    assert validated["answer"] == "Blue"


def test_validator_invalid_answer():
    """Test that invalid answers (not in options) are rejected."""
    # Create the question
    q = QuestionMultipleChoiceWithOther(
        question_name="color",
        question_text="What is your favorite color?",
        question_options=["Red", "Green", "Blue"],
    )

    # Get the validator
    validator = q.response_validator

    # Test with an invalid answer (not in options)
    response = {"answer": "Yellow"}

    # Should raise a validation error
    try:
        validator.validate(response, verbose=False)
        assert False, "Expected validation error for invalid answer"
    except Exception as e:
        # Should be a validation error
        assert (
            "Yellow" in str(e)
            or "Permitted values" in str(e)
            or "validation" in str(e).lower()
        )


def test_validator_other_option_without_colon():
    """Test that 'Other' option without colon format is still valid."""
    # Create the question
    q = QuestionMultipleChoiceWithOther(
        question_name="feeling",
        question_text="How are you feeling?",
        question_options=["Good", "Great", "OK", "Bad"],
    )

    # Get the validator
    validator = q.response_validator

    # Test with just "Other" (without colon format) - it's a valid option
    response = {"answer": "Other"}
    validated = validator.validate(response, verbose=False)

    # Check that it validates correctly - "Other" is a valid option
    assert validated["answer"] == "Other"
