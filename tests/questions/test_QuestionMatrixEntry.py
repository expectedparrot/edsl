import pytest
from edsl.questions.exceptions import QuestionAnswerValidationError
from edsl.questions import QuestionBase
from edsl.questions.question_matrix_entry import QuestionMatrixEntry
from edsl.questions.exceptions import QuestionCreationValidationError

valid_question = {
    "question_name": "ai_trust_satisfaction",
    "question_text": "Rate your trust and satisfaction levels (0-10) for different AI usage scenarios:",
    "question_items": ["Trust level", "Satisfaction level"],
    "question_columns": ["No AI Tools", "With AI Help", "AI Only"],
    "min_value": 0,
    "max_value": 10,
}


def test_QuestionMatrixEntry_construction():
    """Test QuestionMatrixEntry construction."""
    # Basic construction
    q = QuestionMatrixEntry(**valid_question)
    assert isinstance(q, QuestionMatrixEntry)
    assert q.question_name == valid_question["question_name"]
    assert q.question_text == valid_question["question_text"]
    assert q.question_items == valid_question["question_items"]
    assert q.question_columns == valid_question["question_columns"]
    assert q.min_value == valid_question["min_value"]
    assert q.max_value == valid_question["max_value"]

    # Construction without constraints
    q = QuestionMatrixEntry(
        question_name="unconstrained",
        question_text="Rate these items:",
        question_items=["Item1", "Item2"],
        question_columns=["Col1", "Col2"]
    )
    assert q.min_value is None
    assert q.max_value is None

    # Invalid constructions
    with pytest.raises(
        QuestionCreationValidationError,
        match="`question_name` is not a valid variable name",
    ):
        QuestionMatrixEntry(
            question_name="",
            question_text="Test",
            question_items=["Item1"],
            question_columns=["Col1"]
        )

    with pytest.raises(
        QuestionCreationValidationError,
        match="question_text cannot be empty or too short!",
    ):
        QuestionMatrixEntry(
            question_name="test",
            question_text="",
            question_items=["Item1"],
            question_columns=["Col1"]
        )


def test_QuestionMatrixEntry_validation():
    """Test answer validation."""
    q = QuestionMatrixEntry(**valid_question)

    # Valid answer
    valid_answer = {
        "answer": {
            "Trust level": {"No AI Tools": 7.5, "With AI Help": 8.2, "AI Only": 6.1},
            "Satisfaction level": {"No AI Tools": 6.8, "With AI Help": 9.1, "AI Only": 7.3}
        }
    }
    q._validate_answer(valid_answer)

    # Valid answer with integers
    valid_answer_int = {
        "answer": {
            "Trust level": {"No AI Tools": 7, "With AI Help": 8, "AI Only": 6},
            "Satisfaction level": {"No AI Tools": 6, "With AI Help": 9, "AI Only": 7}
        }
    }
    q._validate_answer(valid_answer_int)

    # Missing items
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({"answer": {"Trust level": {"No AI Tools": 7.5, "With AI Help": 8.2, "AI Only": 6.1}}})

    # Missing columns for an item
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({
            "answer": {
                "Trust level": {"No AI Tools": 7.5, "With AI Help": 8.2},  # Missing "AI Only"
                "Satisfaction level": {"No AI Tools": 6.8, "With AI Help": 9.1, "AI Only": 7.3}
            }
        })

    # Out of range values
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({
            "answer": {
                "Trust level": {"No AI Tools": 15.0, "With AI Help": 8.2, "AI Only": 6.1},  # 15.0 > 10
                "Satisfaction level": {"No AI Tools": 6.8, "With AI Help": 9.1, "AI Only": 7.3}
            }
        })

    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({
            "answer": {
                "Trust level": {"No AI Tools": -1.0, "With AI Help": 8.2, "AI Only": 6.1},  # -1.0 < 0
                "Satisfaction level": {"No AI Tools": 6.8, "With AI Help": 9.1, "AI Only": 7.3}
            }
        })


def test_QuestionMatrixEntry_validation_permissive():
    """Test answer validation in permissive mode."""
    q = QuestionMatrixEntry(**{**valid_question, "permissive": True})

    # Out of range values should be allowed in permissive mode
    q._validate_answer({
        "answer": {
            "Trust level": {"No AI Tools": 15.0, "With AI Help": 8.2, "AI Only": 6.1},
            "Satisfaction level": {"No AI Tools": 6.8, "With AI Help": 9.1, "AI Only": 7.3}
        }
    })

    # Missing items should be allowed in permissive mode
    q._validate_answer({"answer": {"Trust level": {"No AI Tools": 7.5, "With AI Help": 8.2, "AI Only": 6.1}}})


def test_QuestionMatrixEntry_serialization():
    """Test serialization."""
    q = QuestionMatrixEntry(**valid_question)
    serialized = q.to_dict()

    assert serialized["question_type"] == "matrix_entry"
    assert serialized["question_name"] == valid_question["question_name"]
    assert serialized["question_items"] == valid_question["question_items"]
    assert serialized["question_columns"] == valid_question["question_columns"]
    assert serialized["min_value"] == valid_question["min_value"]
    assert serialized["max_value"] == valid_question["max_value"]

    deserialized = QuestionBase.from_dict(serialized)
    assert isinstance(deserialized, QuestionMatrixEntry)
    assert deserialized.question_name == q.question_name
    assert deserialized.question_items == q.question_items
    assert deserialized.question_columns == q.question_columns
    assert deserialized.min_value == q.min_value
    assert deserialized.max_value == q.max_value


def test_QuestionMatrixEntry_html():
    """Test HTML generation."""
    q = QuestionMatrixEntry(**valid_question)
    html = q.question_html_content

    assert "table" in html
    assert "matrix-entry-question" in html
    assert all(item in html for item in q.question_items)
    assert all(column in html for column in q.question_columns)
    assert 'type="number"' in html
    assert f'min="{q.min_value}"' in html
    assert f'max="{q.max_value}"' in html
    assert 'step="0.1"' in html


def test_QuestionMatrixEntry_example():
    """Test example creation."""
    q = QuestionMatrixEntry.example()
    assert isinstance(q, QuestionMatrixEntry)
    assert q.question_name == "ai_trust_satisfaction"
    assert len(q.question_items) > 0
    assert len(q.question_columns) > 0
    assert q.min_value == 0
    assert q.max_value == 10


def test_QuestionMatrixEntry_simulation():
    """Test answer simulation."""
    q = QuestionMatrixEntry(**valid_question)
    simulated = q._simulate_answer()

    assert isinstance(simulated, dict)
    assert "answer" in simulated
    assert isinstance(simulated["answer"], dict)
    assert set(simulated["answer"].keys()) == set(q.question_items)

    for item_name, item_responses in simulated["answer"].items():
        assert isinstance(item_responses, dict)
        assert set(item_responses.keys()) == set(q.question_columns)
        for column_name, value in item_responses.items():
            assert isinstance(value, (int, float))
            assert q.min_value <= value <= q.max_value


def test_QuestionMatrixEntry_response_validator_fix_flat_keys():
    """Test the fix for responses with flat keys like 'Trust level.No AI Tools'."""
    q = QuestionMatrixEntry(**valid_question)

    # Test flat keys with dot separator
    flat_response = {
        "answer": {
            "Trust level.No AI Tools": 7.5,
            "Trust level.With AI Help": 8.2,
            "Trust level.AI Only": 6.1,
            "Satisfaction level.No AI Tools": 6.8,
            "Satisfaction level.With AI Help": 9.1,
            "Satisfaction level.AI Only": 7.3
        }
    }

    fixed_response = q.response_validator.fix(flat_response, verbose=True)
    assert isinstance(fixed_response["answer"], dict)
    assert "Trust level" in fixed_response["answer"]
    assert "Satisfaction level" in fixed_response["answer"]
    assert fixed_response["answer"]["Trust level"]["No AI Tools"] == 7.5
    assert fixed_response["answer"]["Satisfaction level"]["AI Only"] == 7.3

    # Test flat keys with underscore separator
    underscore_response = {
        "answer": {
            "Trust level_No AI Tools": 7.5,
            "Trust level_With AI Help": 8.2,
            "Trust level_AI Only": 6.1,
            "Satisfaction level_No AI Tools": 6.8,
            "Satisfaction level_With AI Help": 9.1,
            "Satisfaction level_AI Only": 7.3
        }
    }

    fixed_response = q.response_validator.fix(underscore_response, verbose=True)
    assert isinstance(fixed_response["answer"], dict)
    assert "Trust level" in fixed_response["answer"]
    assert "Satisfaction level" in fixed_response["answer"]


def test_QuestionMatrixEntry_response_validator_fix_string_values():
    """Test the fix for responses with string numeric values."""
    q = QuestionMatrixEntry(**valid_question)

    string_response = {
        "answer": {
            "Trust level": {"No AI Tools": "7.5", "With AI Help": "8.2", "AI Only": "6.1"},
            "Satisfaction level": {"No AI Tools": "6.8", "With AI Help": "9.1", "AI Only": "7.3"}
        }
    }

    fixed_response = q.response_validator.fix(string_response, verbose=True)
    assert isinstance(fixed_response["answer"], dict)
    assert fixed_response["answer"]["Trust level"]["No AI Tools"] == 7.5
    assert fixed_response["answer"]["Satisfaction level"]["AI Only"] == 7.3


def test_QuestionMatrixEntry_response_validator_fix_json_string():
    """Test the fix for responses where answer is a JSON string."""
    q = QuestionMatrixEntry(**valid_question)

    json_response = {
        "answer": '{"Trust level": {"No AI Tools": 7.5, "With AI Help": 8.2, "AI Only": 6.1}, "Satisfaction level": {"No AI Tools": 6.8, "With AI Help": 9.1, "AI Only": 7.3}}'
    }

    fixed_response = q.response_validator.fix(json_response, verbose=True)
    assert isinstance(fixed_response["answer"], dict)
    assert fixed_response["answer"]["Trust level"]["No AI Tools"] == 7.5
    assert fixed_response["answer"]["Satisfaction level"]["AI Only"] == 7.3


def test_QuestionMatrixEntry_response_validator_fix_with_text_extraction():
    """Test the fix for responses with text that contains numeric values."""
    q = QuestionMatrixEntry(**valid_question)

    # Test string with numeric extraction
    text_response = {
        "answer": {
            "Trust level": {"No AI Tools": "I rate this 7.5", "With AI Help": "8.2 out of 10", "AI Only": "6.1"},
            "Satisfaction level": {"No AI Tools": "6.8", "With AI Help": "About 9.1", "AI Only": "Score: 7.3"}
        }
    }

    fixed_response = q.response_validator.fix(text_response, verbose=True)
    assert isinstance(fixed_response["answer"], dict)
    assert fixed_response["answer"]["Trust level"]["No AI Tools"] == 7.5
    assert fixed_response["answer"]["Trust level"]["With AI Help"] == 8.2
    assert fixed_response["answer"]["Satisfaction level"]["With AI Help"] == 9.1


def test_QuestionMatrixEntry_no_constraints():
    """Test QuestionMatrixEntry without min/max constraints."""
    q = QuestionMatrixEntry(
        question_name="unconstrained",
        question_text="Rate these items:",
        question_items=["Item1", "Item2"],
        question_columns=["Col1", "Col2"]
    )

    # Should accept any numeric values
    q._validate_answer({
        "answer": {
            "Item1": {"Col1": -100.5, "Col2": 1000.7},
            "Item2": {"Col1": 0, "Col2": 42}
        }
    })

    # Simulation should still work
    simulated = q._simulate_answer()
    assert isinstance(simulated["answer"], dict)
    assert len(simulated["answer"]) == 2

    # Without constraints, simulation uses default range [0, 10]
    for item_responses in simulated["answer"].values():
        for value in item_responses.values():
            assert isinstance(value, (int, float))
            assert 0 <= value <= 10


def test_QuestionMatrixEntry_edge_cases():
    """Test edge cases and error conditions."""
    q = QuestionMatrixEntry(**valid_question)

    # Test response with no answer field
    no_answer_response = {"comment": "No answer provided"}
    fixed = q.response_validator.fix(no_answer_response, verbose=True)
    assert fixed == no_answer_response  # Should return original if no answer

    # Test response with invalid structure
    invalid_response = {"answer": "not a dict"}
    fixed = q.response_validator.fix(invalid_response, verbose=True)
    # Should attempt to fix but likely return original if unfixable


def test_QuestionMatrixEntry_create_response_model():
    """Test dynamic response model creation."""
    q = QuestionMatrixEntry(**valid_question)
    model_class = q.create_response_model()

    # Test valid response creation
    valid_data = {
        "answer": {
            "Trust level": {"No AI Tools": 7.5, "With AI Help": 8.2, "AI Only": 6.1},
            "Satisfaction level": {"No AI Tools": 6.8, "With AI Help": 9.1, "AI Only": 7.3}
        }
    }
    instance = model_class(**valid_data)
    assert instance.answer.model_dump() == valid_data["answer"]

    # Test that validation catches range violations
    with pytest.raises(Exception):  # Should be validation error
        model_class(answer={
            "Trust level": {"No AI Tools": 15.0, "With AI Help": 8.2, "AI Only": 6.1},  # Out of range
            "Satisfaction level": {"No AI Tools": 6.8, "With AI Help": 9.1, "AI Only": 7.3}
        })


if __name__ == "__main__":
    pytest.main([__file__])