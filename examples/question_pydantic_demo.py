"""
Demo script for QuestionPydantic - Structured Output with Custom Pydantic Models

This example demonstrates how to use QuestionPydantic to get structured responses
from language models that conform to your custom Pydantic models.
"""

from pydantic import BaseModel, Field
from edsl.questions import QuestionPydantic
from edsl.language_models import Model


# Define your custom Pydantic model
class Person(BaseModel):
    """A model representing a person's information."""
    name: str = Field(description="Full name of the person")
    age: int = Field(description="Age in years", ge=0, le=150)
    occupation: str = Field(description="Job title or profession")
    city: str = Field(description="City of residence")


class Product(BaseModel):
    """A model representing a product."""
    name: str = Field(description="Product name")
    price: float = Field(description="Price in USD", gt=0)
    in_stock: bool = Field(description="Whether the product is currently in stock")
    category: str = Field(description="Product category")


def demo_person_extraction():
    """Demonstrate extracting person information."""
    print("=" * 70)
    print("Demo 1: Person Information Extraction")
    print("=" * 70)

    # Create a question with a custom Pydantic model
    q = QuestionPydantic(
        question_name="extract_person",
        question_text="Extract information about the person: John Smith is a 35-year-old software engineer living in San Francisco.",
        pydantic_model=Person
    )

    print(f"\nQuestion: {q.question_text}")
    print(f"\nExpected response structure: {q.user_pydantic_model.__name__}")
    print(f"\nJSON Schema:")
    import json
    print(json.dumps(q.get_response_schema(), indent=2))

    # Simulate an answer (in real use, this would come from an LLM)
    simulated = q._simulate_answer()
    print(f"\nSimulated answer: {simulated['answer']}")


def demo_product_extraction():
    """Demonstrate extracting product information."""
    print("\n" + "=" * 70)
    print("Demo 2: Product Information Extraction")
    print("=" * 70)

    q = QuestionPydantic(
        question_name="extract_product",
        question_text="Extract product details: The Widget Pro costs $49.99, is currently in stock, and belongs to the Electronics category.",
        pydantic_model=Product
    )

    print(f"\nQuestion: {q.question_text}")
    print(f"\nExpected response structure: {q.user_pydantic_model.__name__}")

    # Check the generated JSON schema
    schema = q.get_response_schema()
    print(f"\nRequired fields: {schema.get('required', [])}")

    simulated = q._simulate_answer()
    print(f"\nSimulated answer: {simulated['answer']}")


def demo_validation():
    """Demonstrate validation against the Pydantic model."""
    print("\n" + "=" * 70)
    print("Demo 3: Response Validation")
    print("=" * 70)

    q = QuestionPydantic(
        question_name="validate_person",
        question_text="Extract person info",
        pydantic_model=Person
    )

    # Valid answer
    valid_answer = {
        "answer": {"name": "Alice Johnson", "age": 28, "occupation": "Designer", "city": "Boston"},
        "generated_tokens": "{...}"
    }
    print("\nValidating a correct answer:")
    print(f"Input: {valid_answer['answer']}")
    try:
        validated = q._validate_answer(valid_answer)
        print(f"✓ Validation passed: {validated['answer']}")
    except Exception as e:
        print(f"✗ Validation failed: {e}")

    # Invalid answer (age out of range)
    invalid_answer = {
        "answer": {"name": "Bob Smith", "age": 200, "occupation": "Astronaut", "city": "Mars"},
        "generated_tokens": "{...}"
    }
    print("\nValidating an incorrect answer (age > 150):")
    print(f"Input: {invalid_answer['answer']}")
    try:
        validated = q._validate_answer(invalid_answer)
        print(f"✓ Validation passed: {validated['answer']}")
    except Exception as e:
        print(f"✗ Validation failed: Age constraint violated")


def demo_serialization():
    """Demonstrate serialization and deserialization."""
    print("\n" + "=" * 70)
    print("Demo 4: Serialization and Deserialization")
    print("=" * 70)

    # Create a question
    q1 = QuestionPydantic(
        question_name="serialize_test",
        question_text="Test serialization",
        pydantic_model=Person
    )

    print("\nOriginal question:")
    print(f"  Name: {q1.question_name}")
    print(f"  Model: {q1.user_pydantic_model.__name__}")

    # Serialize to dict
    serialized = q1.to_dict(add_edsl_version=False)
    print(f"\nSerialized keys: {list(serialized.keys())}")
    print(f"  Has pydantic_model_schema: {' pydantic_model_schema' in serialized}")

    # Deserialize back
    from edsl.questions import QuestionBase
    q2 = QuestionBase.from_dict(serialized)
    print(f"\nDeserialized question:")
    print(f"  Name: {q2.question_name}")
    print(f"  Model: {q2.user_pydantic_model.__name__}")
    print(f"  ✓ Round-trip successful!")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("QuestionPydantic: Structured Output with Custom Pydantic Models")
    print("=" * 70)
    print("\nThis demonstrates EDSL's new QuestionPydantic type, which allows")
    print("you to specify arbitrary Pydantic models as response schemas.")
    print("\nWhen using OpenAI models (or other services that support structured")
    print("output), the JSON schema is passed to the LLM to constrain generation.")
    print("For other models, responses are validated post-hoc.")

    demo_person_extraction()
    demo_product_extraction()
    demo_validation()
    demo_serialization()

    print("\n" + "=" * 70)
    print("Demo Complete!")
    print("=" * 70)
    print("\nTo use with a real LLM:")
    print("  q = QuestionPydantic(question_name='...', question_text='...', pydantic_model=YourModel)")
    print("  results = q.by(Model('gpt-4')).run()")
    print("=" * 70 + "\n")
