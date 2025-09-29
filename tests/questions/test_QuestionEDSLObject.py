import pytest
import json
from edsl.questions import QuestionBase
from edsl.questions.question_edsl_object import QuestionEDSLObject, main
from edsl.questions.exceptions import QuestionAnswerValidationError


def test_QuestionEDSLObject_main():
    """Test the main function runs without error."""
    main()


valid_question = {
    "question_name": "create_question",
    "question_text": "Create a free text question about AI.",
    "expected_object_type": "free_text"
}


def test_QuestionEDSLObject_construction():
    """Test QuestionEDSLObject construction."""

    q = QuestionEDSLObject(**valid_question)
    assert isinstance(q, QuestionEDSLObject)
    assert q.question_name == valid_question["question_name"]
    assert q.question_text == valid_question["question_text"]
    assert q.expected_object_type == valid_question["expected_object_type"]
    assert q.question_type == "edsl_object"

    # Test data property includes expected_object_type
    expected_data = valid_question.copy()
    assert q.data == expected_data

    # Should raise an exception if expected_object_type is invalid
    invalid_question = valid_question.copy()
    invalid_question["expected_object_type"] = "nonexistent_type"
    with pytest.raises(ValueError, match="Expected object type 'nonexistent_type' not found in EDSL registries"):
        QuestionEDSLObject(**invalid_question)

    # Should raise an exception if question_text is missing
    invalid_question = valid_question.copy()
    invalid_question.pop("question_text")
    with pytest.raises(TypeError):  # Missing required argument
        QuestionEDSLObject(**invalid_question)

    # Should raise an exception if expected_object_type is missing
    invalid_question = valid_question.copy()
    invalid_question.pop("expected_object_type")
    with pytest.raises(TypeError):  # Missing required argument
        QuestionEDSLObject(**invalid_question)

    # Should raise an exception if unexpected attribute is present
    invalid_question = valid_question.copy()
    invalid_question.update({"unexpected_attribute": "unexpected_value"})
    with pytest.raises(TypeError):  # Unexpected keyword argument
        QuestionEDSLObject(**invalid_question)


def test_QuestionEDSLObject_serialization():
    """Test QuestionEDSLObject serialization and deserialization."""

    q = QuestionEDSLObject(**valid_question)

    # Serialization should include all necessary fields
    serialized = q.to_dict()
    expected_fields = {
        "question_name": "create_question",
        "question_text": "Create a free text question about AI.",
        "question_type": "edsl_object",
        "expected_object_type": "free_text"
    }

    for key, value in expected_fields.items():
        assert serialized[key] == value

    # Deserialization should return a QuestionEDSLObject
    q_deserialized = QuestionBase.from_dict(serialized)
    assert isinstance(q_deserialized, QuestionEDSLObject)
    assert type(q) == type(q_deserialized)
    assert q.question_name == q_deserialized.question_name
    assert q.question_text == q_deserialized.question_text
    assert q.expected_object_type == q_deserialized.expected_object_type

    # Serialization from bad data should raise an exception
    with pytest.raises(Exception):
        QuestionBase.from_dict({"question_type": "edsl_object"})  # Missing required fields

    with pytest.raises(Exception):
        QuestionBase.from_dict({
            "question_type": "edsl_object",
            "question_name": "test",
            "question_text": "test",
            "expected_object_type": "nonexistent_type"
        })


def test_QuestionEDSLObject_validation():
    """Test answer validation for QuestionEDSLObject."""

    q = QuestionEDSLObject(**valid_question)

    # Valid answer: use real EDSL object serialization
    from edsl.questions import QuestionFreeText
    real_ft_question = QuestionFreeText(
        question_name="test_question",
        question_text="What is your favorite color?"
    )
    real_serialized = real_ft_question.to_dict()

    valid_answer = {
        "answer": real_serialized,
        "generated_tokens": json.dumps(real_serialized)
    }

    validated = q._validate_answer(valid_answer)
    assert validated["answer"] == valid_answer["answer"]
    assert "generated_tokens" in validated

    # Invalid answer: not a dictionary
    invalid_answer_1 = {
        "answer": "not a dictionary",
        "generated_tokens": "not a dictionary"
    }

    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer(invalid_answer_1)

    # Invalid answer: dictionary but can't instantiate free text question
    invalid_answer_2 = {
        "answer": {
            "invalid_field": "value",
            "another_invalid": "field"
        },
        "generated_tokens": json.dumps({
            "invalid_field": "value",
            "another_invalid": "field"
        })
    }

    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer(invalid_answer_2)


def test_QuestionEDSLObject_validator_fix():
    """Test the response validator's fix method."""

    q = QuestionEDSLObject(**valid_question)
    validator = q.response_validator

    # Test fixing a JSON string answer using real EDSL serialization
    from edsl.questions import QuestionFreeText
    real_question = QuestionFreeText(
        question_name="fixed_question",
        question_text="Fixed question?"
    )
    real_serialized = real_question.to_dict()

    json_string_response = {
        "answer": json.dumps(real_serialized),
        "generated_tokens": "some tokens"
    }

    fixed = validator.fix(json_string_response, verbose=False)
    assert isinstance(fixed["answer"], dict)
    assert fixed["answer"]["question_type"] == "free_text"
    assert fixed["answer"]["question_name"] == "fixed_question"

    # Test fixing when answer is not a dict but generated_tokens is JSON
    from_tokens_question = QuestionFreeText(
        question_name="from_tokens",
        question_text="From tokens?"
    )
    from_tokens_serialized = from_tokens_question.to_dict()

    malformed_response = {
        "answer": "not a dict",
        "generated_tokens": json.dumps(from_tokens_serialized)
    }

    fixed = validator.fix(malformed_response, verbose=False)
    assert isinstance(fixed["answer"], dict)
    assert fixed["answer"]["question_name"] == "from_tokens"

    # Test fallback to empty dict
    completely_broken = {
        "answer": "not json",
        "generated_tokens": "also not json"
    }

    fixed = validator.fix(completely_broken, verbose=False)
    assert fixed["answer"] == {}


def test_QuestionEDSLObject_validator_instantiation():
    """Test the validator's object instantiation validation."""

    q = QuestionEDSLObject(**valid_question)
    validator = q.response_validator

    # Valid free text question dict - use real EDSL serialization
    from edsl.questions import QuestionFreeText
    test_question = QuestionFreeText(
        question_name="test",
        question_text="Test question?"
    )
    valid_dict = test_question.to_dict()

    assert validator.validate_object_instantiation(valid_dict, "free_text") is True

    # Invalid dict for free text question
    invalid_dict = {
        "invalid_field": "value"
    }

    assert validator.validate_object_instantiation(invalid_dict, "free_text") is False

    # Nonexistent object type
    assert validator.validate_object_instantiation(valid_dict, "nonexistent_type") is False


def test_QuestionEDSLObject_simulate_answer():
    """Test simulated answer generation."""

    q = QuestionEDSLObject(**valid_question)
    simulated = q._simulate_answer()

    assert isinstance(simulated, dict)
    assert "answer" in simulated
    assert "generated_tokens" in simulated
    assert isinstance(simulated["answer"], dict)

    # For free text expected type, should have proper structure
    answer_dict = simulated["answer"]
    assert answer_dict["question_type"] == "free_text"
    assert "question_name" in answer_dict
    assert "question_text" in answer_dict


def test_QuestionEDSLObject_example():
    """Test the example class method."""

    q = QuestionEDSLObject.example()
    assert isinstance(q, QuestionEDSLObject)
    assert q.question_name == "create_question"
    assert q.expected_object_type == "free_text"
    assert "free text question" in q.question_text.lower()

    # Test randomized example
    q1 = QuestionEDSLObject.example(randomize=True)
    q2 = QuestionEDSLObject.example(randomize=True)
    assert q1.question_text != q2.question_text  # Should be different due to UUID


def test_QuestionEDSLObject_html_content():
    """Test HTML content generation."""

    q = QuestionEDSLObject(**valid_question)
    html = q.question_html_content

    assert isinstance(html, str)
    assert q.question_name in html
    assert q.expected_object_type in html
    assert "textarea" in html.lower()
    assert "json" in html.lower()


def test_QuestionEDSLObject_integration_with_different_types():
    """Test the question works with different EDSL object types."""

    # Test with multiple choice expectation
    mc_question = QuestionEDSLObject(
        question_name="create_mc",
        question_text="Create a multiple choice question about colors.",
        expected_object_type="multiple_choice"
    )

    assert mc_question.expected_object_type == "multiple_choice"

    # Simulated answer should adapt to the expected type
    simulated = mc_question._simulate_answer()
    answer_dict = simulated["answer"]

    # Should contain MC-specific fields
    assert "question_type" in answer_dict or "question_options" in answer_dict

def test_QuestionEDSLObject_broader_edsl_objects():
    """Test the question works with broader EDSL objects like ScenarioList."""

    # Test with ScenarioList expectation
    sl_question = QuestionEDSLObject(
        question_name="create_scenarios",
        question_text="Create a scenario list for testing.",
        expected_object_type="ScenarioList"
    )

    assert sl_question.expected_object_type == "ScenarioList"

    # Test with real ScenarioList object
    from edsl import ScenarioList
    import json

    real_sl = ScenarioList.example()
    real_sl_dict = real_sl.to_dict()

    answer = {
        "answer": real_sl_dict,
        "generated_tokens": json.dumps(real_sl_dict)
    }

    # Should validate successfully
    validated = sl_question._validate_answer(answer)
    assert validated["answer"] == real_sl_dict

    # Should simulate ScenarioList format
    simulated = sl_question._simulate_answer()
    answer_dict = simulated["answer"]

    # Should contain ScenarioList-specific structure
    assert "scenarios" in answer_dict


if __name__ == "__main__":
    pytest.main([__file__])