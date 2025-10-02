import pytest
from edsl.questions.exceptions import QuestionAnswerValidationError
from edsl.questions import QuestionDemand


valid_question = {
    "question_text": "How many cups of coffee would you buy per week at each price?",
    "prices": [1.0, 2.0, 3.0, 4.0],
    "question_name": "coffee_demand",
}

valid_question_w_extras = {
    "question_text": "How many cups of coffee would you buy per week at each price?",
    "prices": [1.0, 2.0, 3.0, 4.0],
    "question_name": "coffee_demand",
    "include_comment": True,
}


def test_QuestionDemand_construction():
    """Test QuestionDemand construction."""

    q = QuestionDemand(**valid_question)
    assert isinstance(q, QuestionDemand)
    assert q.question_text == valid_question["question_text"]
    assert q.prices == valid_question["prices"]

    q = QuestionDemand(**valid_question_w_extras)
    assert isinstance(q, QuestionDemand)
    assert q.question_name == valid_question_w_extras["question_name"]
    # Check key attributes are set correctly
    assert q.include_comment == valid_question_w_extras["include_comment"]

    # should raise an exception if question_text is missing
    invalid_question = valid_question.copy()
    invalid_question.pop("question_text")
    with pytest.raises(Exception):
        QuestionDemand(**invalid_question)

    # or if question_text is empty
    invalid_question = valid_question.copy()
    invalid_question.update({"question_text": ""})
    with pytest.raises(Exception):
        QuestionDemand(**invalid_question)

    # should raise an exception if prices is missing
    invalid_question = valid_question.copy()
    invalid_question.pop("prices")
    with pytest.raises(Exception):
        QuestionDemand(**invalid_question)

    # or if prices is empty
    invalid_question = valid_question.copy()
    invalid_question.update({"prices": []})
    with pytest.raises(Exception):
        QuestionDemand(**invalid_question)

    # or has 1 item
    invalid_question.update({"prices": [1.0]})
    with pytest.raises(Exception):
        QuestionDemand(**invalid_question)

    # or has duplicates
    invalid_question.update({"prices": [1.0, 1.0]})
    with pytest.raises(Exception):
        QuestionDemand(**invalid_question)

    # or not of type list of numbers
    invalid_question.update({"prices": ["1.0", "2.0"]})
    with pytest.raises(Exception):
        QuestionDemand(**invalid_question)

    invalid_question.update({"prices": {"price1": 1.0, "price2": 2.0}})
    with pytest.raises(Exception):
        QuestionDemand(**invalid_question)

    # should raise an exception if unexpected attribute is present
    invalid_question = valid_question.copy()
    invalid_question.update({"unexpected_attribute": "unexpected_attribute"})
    with pytest.raises(Exception):
        QuestionDemand(**invalid_question)


def test_QuestionDemand_answers():
    """Test QuestionDemand answer validation."""
    valid_answer = {"answer": [10, 8, 5, 2], "comment": "Typical demand curve"}
    q = QuestionDemand(**valid_question)

    # answer must be a list of numbers
    q._validate_answer(valid_answer)

    # answer value required
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({"answer": None})

    # all price points must have quantities
    invalid_answer = valid_answer.copy()
    invalid_answer.update({"answer": [10, 8, 5]})
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer(invalid_answer)

    # cannot have more quantities than prices
    invalid_answer = valid_answer.copy()
    invalid_answer.update({"answer": [10, 8, 5, 2, 1]})
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer(invalid_answer)

    # quantities cannot be negative
    invalid_answer = valid_answer.copy()
    invalid_answer.update({"answer": [10, -8, 5, 2]})
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer(invalid_answer)

    # zero quantities are allowed
    valid_answer_with_zero = {"answer": [10, 0, 5, 0]}
    q._validate_answer(valid_answer_with_zero)


def test_QuestionDemand_extras():
    """Test QuestionDemand's extra functionalities."""
    q = QuestionDemand(**valid_question)

    # translate
    assert q._translate_answer_code_to_answer([10, 8, 5, 2], {}) == [
        {"$1.00": 10},
        {"$2.00": 8},
        {"$3.00": 5},
        {"$4.00": 2},
    ]

    # _simulate_answer
    simulated_answer = q._simulate_answer()
    assert isinstance(simulated_answer, dict)
    assert "answer" in simulated_answer
    assert "comment" in simulated_answer
    assert isinstance(simulated_answer["answer"], list)
    assert len(simulated_answer["answer"]) == len(q.prices)
    assert all(isinstance(x, (int, float)) for x in simulated_answer["answer"])
    assert all(x >= 0 for x in simulated_answer["answer"])


def test_QuestionDemand_serialization():
    """Test QuestionDemand serialization and deserialization."""
    q = QuestionDemand(**valid_question)

    # Serialize
    serialized = q.to_dict()
    assert serialized["question_type"] == "demand"
    assert serialized["question_name"] == valid_question["question_name"]
    assert serialized["question_text"] == valid_question["question_text"]
    assert serialized["prices"] == valid_question["prices"]

    # Deserialize
    from edsl.questions import QuestionBase
    deserialized = QuestionBase.from_dict(serialized)
    assert deserialized.question_type == q.question_type
    assert deserialized.question_name == q.question_name
    assert deserialized.question_text == q.question_text
    assert deserialized.prices == q.prices


def test_QuestionDemand_example():
    """Test QuestionDemand example method."""
    q = QuestionDemand.example()
    assert isinstance(q, QuestionDemand)
    assert q.question_name == "coffee_demand"
    assert len(q.prices) == 4
    assert all(isinstance(p, float) for p in q.prices)


def test_QuestionDemand_validator_fix():
    """Test QuestionDemand validator fix method."""
    q = QuestionDemand(**valid_question)
    validator = q.response_validator

    # Fix string to list
    response = {"answer": "10, 8, 5, 2"}
    fixed = validator.fix(response)
    assert fixed["answer"] == [10.0, 8.0, 5.0, 2.0]

    # Preserve comment
    response = {"answer": "10, 8, 5, 2", "comment": "My demand"}
    fixed = validator.fix(response)
    assert "comment" in fixed
    assert fixed["comment"] == "My demand"

    # Fix dictionary to list
    response = {"answer": {0: 10, 1: 8, 2: 5, 3: 2}}
    fixed = validator.fix(response)
    assert fixed["answer"] == [10.0, 8.0, 5.0, 2.0]

    # Fix list of strings to floats
    response = {"answer": ["10", "8", "5", "2"]}
    fixed = validator.fix(response)
    assert fixed["answer"] == [10.0, 8.0, 5.0, 2.0]


def test_QuestionDemand_html_content():
    """Test QuestionDemand HTML content generation."""
    q = QuestionDemand(**valid_question)
    html = q.question_html_content

    assert isinstance(html, str)
    assert "demandForm" in html
    assert "table" in html
    assert "$1.00" in html
    assert "$4.00" in html
    assert "Quantity" in html


def test_QuestionDemand_different_prices():
    """Test QuestionDemand with various price configurations."""
    # Integer prices
    q1 = QuestionDemand(
        question_name="test1",
        question_text="Test",
        prices=[1, 2, 3, 4, 5]
    )
    assert len(q1.prices) == 5

    # Float prices with decimals
    q2 = QuestionDemand(
        question_name="test2",
        question_text="Test",
        prices=[0.99, 1.99, 2.99, 3.99]
    )
    assert len(q2.prices) == 4

    # Mixed integer and float prices
    q3 = QuestionDemand(
        question_name="test3",
        question_text="Test",
        prices=[1, 2.5, 3, 4.5, 5]
    )
    assert len(q3.prices) == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
