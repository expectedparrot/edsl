import pytest
from edsl.questions.exceptions import QuestionAnswerValidationError
from edsl.questions import QuestionBase
from edsl.questions.question_matrix import QuestionMatrix
from edsl.questions.exceptions import QuestionCreationValidationError

valid_question = {
    "question_name": "child_happiness",
    "question_text": "How happy would you be with different numbers of children?",
    "question_items": ["No children", "1 child", "2 children", "3 or more children"],
    "question_options": [1, 2, 3, 4, 5],
    "option_labels": {1: "Very sad", 3: "Neutral", 5: "Extremely happy"},
}


def test_QuestionMatrix_construction():
    """Test QuestionMatrix construction."""
    # Basic construction
    q = QuestionMatrix(**valid_question)
    assert isinstance(q, QuestionMatrix)
    assert q.question_name == valid_question["question_name"]
    assert q.question_text == valid_question["question_text"]
    assert q.question_items == valid_question["question_items"]
    assert q.question_options == valid_question["question_options"]
    assert q.option_labels == valid_question["option_labels"]

    # Construction without labels
    q = QuestionMatrix(
        **{k: v for k, v in valid_question.items() if k != "option_labels"}
    )
    assert q.option_labels == {}

    # Invalid constructions
    with pytest.raises(
        QuestionCreationValidationError,
        match="`question_name` is not a valid variable name",
    ):
        QuestionMatrix(
            question_name="",
            **{k: v for k, v in valid_question.items() if k != "question_name"}
        )

    with pytest.raises(
        QuestionCreationValidationError,
        match="question_text cannot be empty or too short!",
    ):
        QuestionMatrix(
            question_text="",
            **{k: v for k, v in valid_question.items() if k != "question_text"}
        )

    with pytest.raises(
        QuestionCreationValidationError, match="Too few question options"
    ):
        QuestionMatrix(
            question_items=[],
            **{k: v for k, v in valid_question.items() if k != "question_items"}
        )

    with pytest.raises(
        QuestionCreationValidationError, match="Too few question options"
    ):
        QuestionMatrix(
            question_options=[],
            **{k: v for k, v in valid_question.items() if k != "question_options"}
        )


def test_QuestionMatrix_validation():
    """Test answer validation."""
    q = QuestionMatrix(**valid_question)

    # Valid answer
    valid_answer = {
        "answer": {
            "No children": 1,
            "1 child": 2,
            "2 children": 3,
            "3 or more children": 4,
        }
    }
    q._validate_answer(valid_answer)

    # Missing items
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({"answer": {"No children": 1, "1 child": 2}})

    # Invalid options
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer(
            {
                "answer": {
                    "No children": 1,
                    "1 child": 2,
                    "2 children": 6,
                    "3 or more children": 4,
                }
            }
        )


def test_QuestionMatrix_serialization():
    """Test serialization."""
    q = QuestionMatrix(**valid_question)
    serialized = q.to_dict()

    assert serialized["question_type"] == "matrix"
    assert serialized["question_name"] == valid_question["question_name"]
    assert serialized["question_items"] == valid_question["question_items"]
    assert serialized["question_options"] == valid_question["question_options"]

    deserialized = QuestionBase.from_dict(serialized)
    assert isinstance(deserialized, QuestionMatrix)
    assert deserialized.question_name == q.question_name
    assert deserialized.question_items == q.question_items
    assert deserialized.question_options == q.question_options


def test_QuestionMatrix_html():
    """Test HTML generation."""
    q = QuestionMatrix(**valid_question)
    html = q.question_html_content

    assert "table" in html
    assert "matrix-question" in html
    assert all(item in html for item in q.question_items)
    assert all(str(option) in html for option in q.question_options)
    assert all(label in html for label in q.option_labels.values())


def test_QuestionMatrix_example():
    """Test example creation."""
    q = QuestionMatrix.example()
    assert isinstance(q, QuestionMatrix)
    assert q.question_name == "child_happiness"
    assert len(q.question_items) > 0
    assert len(q.question_options) > 0
    assert len(q.option_labels) > 0


def test_QuestionMatrix_simulation():
    """Test answer simulation."""
    q = QuestionMatrix(**valid_question)
    simulated = q._simulate_answer()

    assert isinstance(simulated, dict)
    assert "answer" in simulated
    assert isinstance(simulated["answer"], dict)
    assert set(simulated["answer"].keys()) == set(q.question_items)
    assert all(answer in q.question_options for answer in simulated["answer"].values())


def test_QuestionMatrix_numeric_key_fix():
    """Test the fix for responses with numeric keys like {"0": 1, "1": 3, "2": 0}."""
    # Use permissive mode to avoid validation failures
    q = QuestionMatrix(
        question_name="test_numeric_keys",
        question_text="How often do you use each of the following?",
        question_items=["Use TikTok", "Use Instagram", "Use BlueSky"],
        question_options=["Never", "Rarely", "Now and then", "Quite regularly", "Very regularly"],
        permissive=True
    )

    # This is the format that caused the validation error in production
    numeric_response = {
        "answer": {"0": 1, "1": 3, "2": 0},
        "comment": "I rarely use TikTok, quite regularly use Instagram, and never use BlueSky.",
        "generated_tokens": '{"0": 1, "1": 3, "2": 0}\n\nI rarely use TikTok, quite regularly use Instagram, and never use BlueSky.'
    }

    # First test the direct fix method to see if it correctly converts the response
    fixed_response = q.response_validator.fix(numeric_response, verbose=True)
    
    # Assert each item is in the fixed response
    assert "Use TikTok" in fixed_response["answer"]
    assert "Use Instagram" in fixed_response["answer"]
    assert "Use BlueSky" in fixed_response["answer"]
    
    # Check that all items are present
    assert len(fixed_response["answer"]) == len(q.question_items)
    
    # Now create a production-like test with string options
    q2 = QuestionMatrix(
        question_name="test_numeric_keys_string_options",
        question_text="How often do you use each of the following?",
        question_items=["Use TikTok", "Use Instagram", "Use BlueSky"],
        question_options=["Never", "Rarely", "Now and then", "Quite regularly", "Very regularly"],
    )
    
    # Set up generated tokens with the JSON format that's causing the issue
    response_with_json = {
        "answer": {"0": 1, "1": 3, "2": 0},
        "comment": "I rarely use TikTok, quite regularly use Instagram, and never use BlueSky.",
        "generated_tokens": '{"0": 1, "1": 3, "2": 0}'
    }
    
    # This should now work because our fix properly maps numeric keys to item names and values to option strings
    try:
        fixed_data = q2.response_validator.fix(response_with_json, verbose=True)
        # If any item is missing from the fixed data, the test will fail
        assert "Use TikTok" in fixed_data["answer"]
        assert "Use Instagram" in fixed_data["answer"]
        assert "Use BlueSky" in fixed_data["answer"]
    except Exception as e:
        assert False, f"Failed to fix a response with numeric keys: {e}"


if __name__ == "__main__":
    pytest.main([__file__])
