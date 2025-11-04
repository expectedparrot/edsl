"""Tests for QuestionPydantic question type.

This module tests the QuestionPydantic question type, which allows users to
specify arbitrary Pydantic models as response schemas for structured output.
"""

import pytest
from pydantic import BaseModel, Field
from edsl.questions import QuestionPydantic
from edsl.questions.exceptions import QuestionAnswerValidationError


class SimplePerson(BaseModel):
    """Simple Pydantic model for testing."""
    name: str = Field(description="Person's full name")
    age: int = Field(description="Person's age in years", ge=0, le=150)


class Product(BaseModel):
    """Product model for testing."""
    name: str = Field(description="Product name")
    price: float = Field(description="Price in dollars", gt=0)
    in_stock: bool = Field(description="Whether product is in stock")


class ComplexModel(BaseModel):
    """Complex nested model for testing."""
    title: str
    items: list[str]
    metadata: dict[str, str]


class TestQuestionPydanticConstruction:
    """Test QuestionPydantic construction and basic properties."""

    def test_construction_with_simple_model(self):
        """Test creating a QuestionPydantic with a simple model."""
        q = QuestionPydantic(
            question_name="extract_person",
            question_text="Extract person info",
            pydantic_model=SimplePerson
        )
        assert q.question_type == "pydantic"
        assert q.question_name == "extract_person"
        assert q.user_pydantic_model == SimplePerson

    def test_construction_with_complex_model(self):
        """Test creating a QuestionPydantic with a complex model."""
        q = QuestionPydantic(
            question_name="extract_data",
            question_text="Extract structured data",
            pydantic_model=ComplexModel
        )
        assert q.user_pydantic_model == ComplexModel

    def test_construction_with_invalid_model(self):
        """Test that construction fails with non-Pydantic model."""
        with pytest.raises(TypeError, match="must be a Pydantic BaseModel subclass"):
            QuestionPydantic(
                question_name="test",
                question_text="Test",
                pydantic_model=dict  # Not a Pydantic model
            )

    def test_example_method(self):
        """Test the example class method."""
        q = QuestionPydantic.example()
        assert q.question_name == "extract_person"
        assert q.user_pydantic_model.__name__ == "Person"


class TestQuestionPydanticSchema:
    """Test JSON schema generation from Pydantic models."""

    def test_get_response_schema_simple(self):
        """Test schema generation for simple model."""
        q = QuestionPydantic(
            question_name="test",
            question_text="Test",
            pydantic_model=SimplePerson
        )
        schema = q.get_response_schema()
        assert "properties" in schema
        assert "name" in schema["properties"]
        assert "age" in schema["properties"]

    def test_get_response_schema_with_descriptions(self):
        """Test that field descriptions are included in schema."""
        q = QuestionPydantic(
            question_name="test",
            question_text="Test",
            pydantic_model=SimplePerson
        )
        schema = q.get_response_schema()
        name_field = schema["properties"]["name"]
        assert "description" in name_field
        assert "full name" in name_field["description"].lower()

    def test_get_response_schema_with_constraints(self):
        """Test that field constraints are included in schema."""
        q = QuestionPydantic(
            question_name="test",
            question_text="Test",
            pydantic_model=SimplePerson
        )
        schema = q.get_response_schema()
        age_field = schema["properties"]["age"]
        # Pydantic includes minimum/maximum in schema
        assert "minimum" in age_field or "ge" in str(age_field)


class TestQuestionPydanticValidation:
    """Test answer validation against Pydantic models."""

    def test_validate_valid_answer(self):
        """Test validation of a valid answer."""
        q = QuestionPydantic(
            question_name="test",
            question_text="Test",
            pydantic_model=SimplePerson
        )
        answer = {
            "answer": {"name": "Alice", "age": 30},
            "generated_tokens": '{"name": "Alice", "age": 30}'
        }
        validated = q._validate_answer(answer)
        assert validated["answer"]["name"] == "Alice"
        assert validated["answer"]["age"] == 30

    def test_validate_invalid_answer_missing_field(self):
        """Test validation fails when required field is missing."""
        q = QuestionPydantic(
            question_name="test",
            question_text="Test",
            pydantic_model=SimplePerson
        )
        answer = {
            "answer": {"name": "Alice"},  # Missing 'age'
            "generated_tokens": '{"name": "Alice"}'
        }
        with pytest.raises(QuestionAnswerValidationError):
            q._validate_answer(answer)

    def test_validate_invalid_answer_wrong_type(self):
        """Test validation fails when field has wrong type."""
        q = QuestionPydantic(
            question_name="test",
            question_text="Test",
            pydantic_model=SimplePerson
        )
        answer = {
            "answer": {"name": "Alice", "age": "thirty"},  # age should be int
            "generated_tokens": '{"name": "Alice", "age": "thirty"}'
        }
        with pytest.raises(QuestionAnswerValidationError):
            q._validate_answer(answer)

    def test_validate_invalid_answer_constraint_violation(self):
        """Test validation fails when constraint is violated."""
        q = QuestionPydantic(
            question_name="test",
            question_text="Test",
            pydantic_model=SimplePerson
        )
        answer = {
            "answer": {"name": "Alice", "age": 200},  # age > 150
            "generated_tokens": '{"name": "Alice", "age": 200}'
        }
        with pytest.raises(QuestionAnswerValidationError):
            q._validate_answer(answer)


class TestQuestionPydanticSerialization:
    """Test serialization and deserialization."""

    def test_to_dict(self):
        """Test serialization to dictionary."""
        q = QuestionPydantic(
            question_name="test",
            question_text="Test question",
            pydantic_model=SimplePerson
        )
        d = q.to_dict(add_edsl_version=False)
        assert d["question_type"] == "pydantic"
        assert d["question_name"] == "test"
        assert d["question_text"] == "Test question"

    def test_round_trip_serialization(self):
        """Test that serialization and deserialization preserves the question."""
        q1 = QuestionPydantic(
            question_name="test",
            question_text="Test question",
            pydantic_model=Product
        )
        d = q1.to_dict(add_edsl_version=False)
        q2 = QuestionPydantic.from_dict(d)
        assert q2.question_name == q1.question_name
        assert q2.question_text == q1.question_text
        assert q2.question_type == q1.question_type


class TestQuestionPydanticSimulation:
    """Test answer simulation."""

    def test_simulate_answer(self):
        """Test that _simulate_answer generates valid data."""
        q = QuestionPydantic(
            question_name="test",
            question_text="Test",
            pydantic_model=SimplePerson
        )
        simulated = q._simulate_answer()
        assert "answer" in simulated
        assert "generated_tokens" in simulated
        # The simulated answer should validate
        validated = q._validate_answer(simulated)
        assert validated is not None

    def test_simulate_answer_complex_model(self):
        """Test simulation with complex model."""
        q = QuestionPydantic(
            question_name="test",
            question_text="Test",
            pydantic_model=Product
        )
        simulated = q._simulate_answer()
        # Should create valid data
        validated = q._validate_answer(simulated)
        assert validated["answer"]["name"] == "example"


class TestQuestionPydanticIntegration:
    """Integration tests with language models."""

    def test_construction_and_prompts(self):
        """Test that QuestionPydantic constructs properly and generates prompts."""
        q = QuestionPydantic(
            question_name="extract_person",
            question_text="Extract person info: Alice is 30 years old",
            pydantic_model=SimplePerson
        )

        # Test that prompts can be generated without errors
        try:
            prompts = q.prompt_preview()
            assert prompts is not None
            assert len(prompts.text) > 0
        except Exception as e:
            pytest.fail(f"Failed to generate prompts: {e}")

    def test_example_generation(self):
        """Test that the example method works."""
        q = QuestionPydantic.example()
        assert q.question_name == "extract_person"

        # Test that it can generate a simulated answer
        simulated = q._simulate_answer()
        assert "answer" in simulated
        assert isinstance(simulated["answer"], dict)


class TestQuestionPydanticResponseValidator:
    """Test the PydanticResponseValidator."""

    def test_validator_fix_json_string(self):
        """Test that validator can fix JSON string answers."""
        q = QuestionPydantic(
            question_name="test",
            question_text="Test",
            pydantic_model=SimplePerson
        )
        validator = q.response_validator

        # Answer as JSON string instead of dict
        response = {
            "answer": '{"name": "Bob", "age": 25}',
            "generated_tokens": '{"name": "Bob", "age": 25}'
        }
        fixed = validator.fix(response)
        assert isinstance(fixed["answer"], dict)
        assert fixed["answer"]["name"] == "Bob"

    def test_validator_fix_from_generated_tokens(self):
        """Test that validator can extract answer from generated_tokens."""
        q = QuestionPydantic(
            question_name="test",
            question_text="Test",
            pydantic_model=SimplePerson
        )
        validator = q.response_validator

        # No answer, but valid generated_tokens
        response = {
            "answer": None,
            "generated_tokens": '{"name": "Charlie", "age": 35}'
        }
        fixed = validator.fix(response)
        assert fixed["answer"]["name"] == "Charlie"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
