import pytest
from pydantic import BaseModel, Field
from typing import Optional, Any
from decimal import Decimal

from edsl.questions.exceptions import QuestionAnswerValidationError
from abc import ABC, abstractmethod

from edsl.questions.response_validator_abc import ResponseValidatorABC
from edsl.questions.data_structures import BaseResponse


class MockResponseModel(BaseResponse):
    answer: int = Field(..., ge=0, le=100)
    comment: Optional[str] = None


class MockValidator(ResponseValidatorABC):
    required_params = ["min_value", "max_value"]
    valid_examples = [{"answer": 50, "comment": "Valid answer"}]
    invalid_examples = [{"answer": 150, "comment": "Invalid answer"}]


# Tests
def test_validator_initialization():
    validator = MockValidator(
        response_model=MockResponseModel, min_value=0, max_value=100
    )
    assert validator.min_value == 0
    assert validator.max_value == 100
    assert validator.response_model == MockResponseModel


def test_validator_missing_params():
    with pytest.raises(ValueError, match="Missing required parameters"):
        MockValidator(response_model=MockResponseModel, min_value=0)


def test_validator_valid_input():
    validator = MockValidator(
        response_model=MockResponseModel, min_value=0, max_value=100
    )
    result = validator.validate({"answer": 50, "comment": "Valid answer"})
    assert result["answer"] == 50
    assert result["comment"] == "Valid answer"


def test_validator_invalid_input():
    validator = MockValidator(
        response_model=MockResponseModel, min_value=0, max_value=100
    )
    with pytest.raises(QuestionAnswerValidationError):
        validator.validate({"answer": 150, "comment": "Invalid answer"})


def test_validator_permissive_mode():
    validator = MockValidator(
        response_model=MockResponseModel, min_value=30, max_value=70, permissive=True
    )
    result = validator.validate({"answer": 20, "comment": "Below min value"})
    assert result["answer"] == 20


def test_validator_override_answer():
    override = {"answer": 42, "comment": "Overridden answer"}
    validator = MockValidator(
        response_model=MockResponseModel,
        min_value=0,
        max_value=100,
        override_answer=override,
    )
    result = validator.validate({"answer": 50, "comment": "Original answer"})
    assert result["answer"] == override["answer"]
    assert result["comment"] == override["comment"]
    assert "generated_tokens" in result
    assert result["generated_tokens"] is None


def test_validator_exception_to_throw():
    custom_exception = ValueError("Custom exception")
    validator = MockValidator(
        response_model=MockResponseModel,
        min_value=0,
        max_value=100,
        exception_to_throw=custom_exception,
    )
    with pytest.raises(ValueError, match="Custom exception"):
        validator.validate({"answer": 50, "comment": "Valid answer"})


# Add more tests as needed to cover other aspects of the ResponseValidatorABC class
