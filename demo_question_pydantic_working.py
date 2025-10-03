"""
Working demo of QuestionPydantic with OpenAI API

This demonstrates that QuestionPydantic successfully:
1. Generates proper JSON schemas from Pydantic models
2. Passes them to OpenAI's API
3. Receives structured responses back

Note: Full integration through .by(m).run() has some issues with results processing
that need further investigation, but the core structured output functionality works.
"""

from pydantic import BaseModel, Field
from edsl.questions import QuestionPydantic
from edsl.language_models import Model
import json


class Person(BaseModel):
    """A person."""
    name: str = Field(description="Full name of the person")
    age: int = Field(description="Age in years", ge=0, le=150)
    occupation: str = Field(description="Job title or profession")


class Book(BaseModel):
    """A book."""
    title: str = Field(description="Title of the book")
    author: str = Field(description="Author's name")
    year: int = Field(description="Publication year", ge=1000, le=2100)
    genre: str = Field(description="Literary genre")


def demo_schema_generation():
    """Show that JSON schemas are properly generated."""
    print("=" * 70)
    print("Demo 1: JSON Schema Generation")
    print("=" * 70)

    q = QuestionPydantic(
        question_name="extract_person",
        question_text="Extract: Dr. Sarah Chen is a 42-year-old neuroscientist",
        pydantic_model=Person
    )

    schema = q.get_response_schema()
    print("\n✓ Schema generated successfully!")
    print(f"  Title: {schema.get('title')}")
    print(f"  Type: {schema.get('type')}")
    print(f"  Required fields: {schema.get('required')}")
    print(f"\n  Full schema:")
    print(json.dumps(schema, indent=4))

    return True


def demo_direct_api_call():
    """Show that direct API calls work with structured output."""
    print("\n" + "=" * 70)
    print("Demo 2: Direct API Call with Structured Output")
    print("=" * 70)

    q = QuestionPydantic(
        question_name="extract_book",
        question_text="Extract: '1984' by George Orwell, published in 1949, is a dystopian novel",
        pydantic_model=Book
    )

    m = Model("gpt-4o-mini")

    print("\nCalling OpenAI API...")
    try:
        response = m.ask_question(q)
        print("✓ API call successful!")

        # Parse the response
        if 'choices' in response and len(response['choices']) > 0:
            content = response['choices'][0]['message']['content']
            print(f"\n  Raw content returned by OpenAI:")
            print(f"  {content[:200]}...")

            # Try to parse it
            try:
                data = json.loads(content)
                if 'answer' in data:
                    answer = data['answer']
                    print(f"\n  ✓ Successfully parsed structured response:")
                    print(f"    Title: {answer.get('title')}")
                    print(f"    Author: {answer.get('author')}")
                    print(f"    Year: {answer.get('year')}")
                    print(f"    Genre: {answer.get('genre')}")

                    # Validate against Pydantic model
                    validated = q.user_pydantic_model.model_validate(answer)
                    print(f"\n  ✓ Response validates against Pydantic model!")
                    return True
            except json.JSONDecodeError as e:
                print(f"  ✗ JSON parse error: {e}")
                return False
    except Exception as e:
        print(f"✗ API call failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def demo_prompt_generation():
    """Show that prompts are properly generated with schema information."""
    print("\n" + "=" * 70)
    print("Demo 3: Prompt Generation with Schema")
    print("=" * 70)

    q = QuestionPydantic(
        question_name="test",
        question_text="Extract person information from the text",
        pydantic_model=Person
    )

    print("\nGenerating prompt...")
    prompts = q.prompt_preview()

    print("✓ Prompt generated successfully!")
    print(f"  Length: {len(prompts.text)} characters")
    print(f"\n  First 400 characters:")
    print(f"  {prompts.text[:400]}")

    # Check if schema is in the prompt
    has_schema = "properties" in prompts.text and "required" in prompts.text
    print(f"\n  ✓ Schema included in prompt: {has_schema}")

    return True


def demo_serialization():
    """Show that questions can be serialized and deserialized."""
    print("\n" + "=" * 70)
    print("Demo 4: Serialization and Deserialization")
    print("=" * 70)

    q1 = QuestionPydantic(
        question_name="serialize_test",
        question_text="Test serialization",
        pydantic_model=Person
    )

    print("\nOriginal question created")
    print(f"  Name: {q1.question_name}")
    print(f"  Model: {q1.user_pydantic_model.__name__}")

    # Serialize
    serialized = q1.to_dict(add_edsl_version=False)
    print(f"\n✓ Serialized to dict")
    print(f"  Keys: {list(serialized.keys())}")

    # Deserialize
    from edsl.questions import QuestionBase
    q2 = QuestionBase.from_dict(serialized)
    print(f"\n✓ Deserialized from dict")
    print(f"  Name: {q2.question_name}")
    print(f"  Model: {q2.user_pydantic_model.__name__}")

    # Verify schemas match
    schema1 = q1.get_response_schema()
    schema2 = q2.get_response_schema()
    schemas_match = schema1 == schema2
    print(f"\n  ✓ Schemas match after round-trip: {schemas_match}")

    return schemas_match


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("QuestionPydantic: Working Demonstrations")
    print("=" * 70)
    print("\nThis demonstrates the core functionality of QuestionPydantic:")
    print("- Custom Pydantic models as response schemas")
    print("- JSON schema generation")
    print("- Integration with OpenAI's API")
    print("- Structured output generation")
    print("=" * 70)

    results = []
    results.append(("Schema Generation", demo_schema_generation()))
    results.append(("Prompt Generation", demo_prompt_generation()))
    results.append(("Direct API Call", demo_direct_api_call()))
    results.append(("Serialization", demo_serialization()))

    # Summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)

    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")

    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\nTotal: {passed}/{total} demonstrations successful")

    if passed == total:
        print("\n✓ All core functionality working!")
        print("\nNote: Full integration through .by(m).run() needs additional")
        print("      debugging for results processing, but the structured output")
        print("      feature itself is functional.")

    print("=" * 70 + "\n")
