import pytest
from edsl.exceptions.questions import QuestionAnswerValidationError
from edsl.questions.QuestionBase import QuestionBase
from edsl.questions.QuestionDict import QuestionDict
from edsl.exceptions.questions import QuestionCreationValidationError

valid_question = {
    "question_name": "recipe",
    "question_text": "Please provide a recipe for basic hot chocolate.",
    "answer_keys": ["recipe_name", "ingredients", "num_ingredients"],
    "value_types": [str, str, list[str], int],
    "value_descriptions": ["The name of the recipe.", "List of ingredients.", "The number of ingredients."],
}


def test_QuestionDict_construction():
    """Test QuestionDict construction."""
    # Basic construction
    q = QuestionDict(**valid_question)
    assert isinstance(q, QuestionDict)
    assert q.question_name == valid_question["question_name"]
    assert q.question_text == valid_question["question_text"]
    assert q.answer_keys == valid_question["answer_keys"]
    assert q.value_types == valid_question["value_types"]
    assert q.value_descriptions == valid_question["value_descriptions"]

    # Construction without value types and descriptions
    q = QuestionDict(
        **{k: v for k, v in valid_question.items() if k not in ["value_types", "value_descriptions"]}
    )
    assert q.value_types == [str] * len(valid_question["answer_keys"])
    assert q.value_descriptions == [""] * len(valid_question["answer_keys"])

    # Invalid constructions
    with pytest.raises(
        QuestionCreationValidationError,
        match="`question_name` is not a valid variable name",
    ):
        QuestionDict(
            question_name="",
            **{k: v for k, v in valid_question.items() if k != "question_name"}
        )

    with pytest.raises(
        QuestionCreationValidationError,
        match="question_text cannot be empty or too short!",
    ):
        QuestionDict(
            question_text="",
            **{k: v for k, v in valid_question.items() if k != "question_text"}
        )
    
    # add tests


def test_QuestionDict_validation():
    """Test answer validation."""
    q = QuestionDict(**valid_question)

    # Valid answer
    valid_answer = {
        "answer": {
            "recipe_name": "Basic Hot Chocolate", 
            "ingredients": ["Steamed milk", "Chocolate flakes"], 
            "num_ingredients": 2
        }
    }
    q._validate_answer(valid_answer)

    # add tests


def test_QuestionDict_serialization():
    """Test serialization."""
    q = QuestionDict(**valid_question)
    serialized = q.to_dict()

    assert serialized["question_type"] == "dict"
    assert serialized["question_name"] == valid_question["question_name"]
    assert serialized["answer_keys"] == valid_question["answer_keys"]

    deserialized = QuestionBase.from_dict(serialized)
    assert isinstance(deserialized, QuestionDict)
    assert deserialized.question_name == q.question_name
    assert deserialized.answer_keys == q.answer_keys


def test_QuestionMatrix_html():
    """Test HTML generation."""
    q = QuestionDict(**valid_question)
    html = q.question_html_content

    assert "table" in html
    assert "dict-question" in html
    assert all(item in html for item in q.question_items)
    assert all(str(key) in html for key in q.answer_keys)


def test_QuestionDict_example():
    """Test example creation."""
    q = QuestionDict.example()
    assert isinstance(q, QuestionDict)
    assert q.question_name == "child_happiness"
    assert len(q.question_items) > 0
    assert len(q.answer_keys) > 0


def test_QuestionDict_simulation():
    """Test answer simulation."""
    q = QuestionDict(**valid_question)
    simulated = q._simulate_answer()

    assert isinstance(simulated, dict)
    assert "answer" in simulated
    assert isinstance(simulated["answer"], dict)
    assert set(simulated["answer"].keys()) == set(q.answer_keys)


if __name__ == "__main__":
    pytest.main([__file__])
