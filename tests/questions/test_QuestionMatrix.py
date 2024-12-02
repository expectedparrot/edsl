import pytest
from edsl.exceptions import (
    QuestionAnswerValidationError,
    QuestionResponseValidationError,
)
from edsl.questions.QuestionBase import QuestionBase
from edsl.questions.QuestionMatrix import QuestionMatrix


valid_question = {
    "question_name": "child_happiness",
    "question_text": "How happy would you be with different numbers of children?",
    "question_items": ["No children", "1 child", "2 children", "3 or more children"],
    "question_options": [1, 2, 3, 4, 5],
    "option_labels": {1: "Very sad", 3: "Neutral", 5: "Extremely happy"},
}

valid_question_wo_labels = {
    "question_name": "child_happiness",
    "question_text": "How happy would you be with different numbers of children?",
    "question_items": ["No children", "1 child", "2 children", "3 or more children"],
    "question_options": [1, 2, 3, 4, 5],
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
    q = QuestionMatrix(**valid_question_wo_labels)
    assert q.option_labels == {}

    # Should raise exceptions for invalid construction
    with pytest.raises(Exception):
        QuestionMatrix(
            question_name="",
            question_text="test",
            question_items=[],
            question_options=[1, 2, 3],
        )

    with pytest.raises(Exception):
        QuestionMatrix(
            question_name="test",
            question_text="",
            question_items=["item1"],
            question_options=[1, 2, 3],
        )

    with pytest.raises(Exception):
        QuestionMatrix(
            question_name="test",
            question_text="test",
            question_items=[],  # Empty items list
            question_options=[1, 2, 3],
        )

    with pytest.raises(Exception):
        QuestionMatrix(
            question_name="test",
            question_text="test",
            question_items=["item1"],
            question_options=[],  # Empty options list
        )


def test_QuestionMatrix_serialization():
    """Test QuestionMatrix serialization."""
    q = QuestionMatrix(**valid_question)

    # Test serialization
    serialized = q.to_dict()
    assert serialized["question_type"] == "matrix"
    assert serialized["question_name"] == valid_question["question_name"]
    assert serialized["question_text"] == valid_question["question_text"]
    assert serialized["question_items"] == valid_question["question_items"]
    assert serialized["question_options"] == valid_question["question_options"]
    assert serialized["option_labels"] == valid_question["option_labels"]

    # Test deserialization
    q_deserialized = QuestionBase.from_dict(serialized)
    assert isinstance(q_deserialized, QuestionMatrix)
    assert q_deserialized.question_name == q.question_name
    assert q_deserialized.question_text == q.question_text
    assert q_deserialized.question_items == q.question_items
    assert q_deserialized.question_options == q.question_options
    assert q_deserialized.option_labels == q.option_labels


def test_QuestionMatrix_validation():
    """Test answer validation for QuestionMatrix."""
    q = QuestionMatrix(**valid_question)

    # Valid answer
    valid_answer = {
        "answer": {
            "No children": 1,
            "1 child": 3,
            "2 children": 4,
            "3 or more children": 5,
        }
    }
    q._validate_answer(valid_answer)

    # Missing items
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer(
            {
                "answer": {
                    "No children": 1,
                    "1 child": 3,
                    # Missing "2 children" and "3 or more children"
                }
            }
        )

    # Invalid option
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer(
            {
                "answer": {
                    "No children": 1,
                    "1 child": 3,
                    "2 children": 6,  # 6 is not in question_options
                    "3 or more children": 5,
                }
            }
        )

    # Extra items
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer(
            {
                "answer": {
                    "No children": 1,
                    "1 child": 3,
                    "2 children": 4,
                    "3 or more children": 5,
                    "4 children": 2,  # Extra item
                }
            }
        )

    # Wrong type (not a dict)
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({"answer": [1, 3, 4, 5]})


def test_QuestionMatrix_html():
    """Test HTML generation for QuestionMatrix."""
    q = QuestionMatrix(**valid_question)
    html = q.question_html_content

    # Basic checks for HTML content
    assert "table" in html
    assert "matrix-question" in html
    assert all(item in html for item in q.question_items)
    assert all(str(option) in html for option in q.question_options)
    assert all(label in html for label in q.option_labels.values())


def test_QuestionMatrix_example():
    """Test the example method of QuestionMatrix."""
    q = QuestionMatrix.example()
    assert isinstance(q, QuestionMatrix)
    assert q.question_name == "child_happiness"
    assert len(q.question_items) > 0
    assert len(q.question_options) > 0
    assert len(q.option_labels) > 0


def test_QuestionMatrix_simulation():
    """Test answer simulation for QuestionMatrix."""
    q = QuestionMatrix(**valid_question)
    simulated = q._simulate_answer()

    assert isinstance(simulated, dict)
    assert "answer" in simulated
    assert isinstance(simulated["answer"], dict)
    assert set(simulated["answer"].keys()) == set(q.question_items)
    assert all(answer in q.question_options for answer in simulated["answer"].values())


if __name__ == "__main__":
    pytest.main([__file__])
