"""
Simple test of QuestionPydantic with OpenAI API
"""

from pydantic import BaseModel, Field
from edsl.questions import QuestionPydantic
from edsl.language_models import Model


class Person(BaseModel):
    """A person."""
    name: str = Field(description="Full name")
    age: int = Field(description="Age in years", ge=0, le=150)


print("Creating QuestionPydantic...")
q = QuestionPydantic(
    question_name="extract_person",
    question_text="Extract: Alice Johnson is 28 years old",
    pydantic_model=Person
)

print(f"Question created: {q.question_name}")
print(f"Model: {q.user_pydantic_model.__name__}")

print("\nGenerating prompt preview...")
prompts = q.prompt_preview()
print(f"Prompt length: {len(prompts.text)} characters")
print("\nFirst 300 chars of prompt:")
print(prompts.text[:300])

print("\n" + "="*70)
print("Running with OpenAI gpt-4o-mini...")
print("="*70)

m = Model("gpt-4o-mini")

try:
    results = q.by(m).run()

    print(f"\nResults type: {type(results)}")
    print(f"Results length: {len(results)}")

    # Try different ways to access the answer
    print("\nTrying to access answer...")

    # Method 1: Direct column access
    if hasattr(results, 'columns'):
        print(f"Available columns: {results.columns}")

    # Method 2: Try to get the data
    try:
        df = results.to_pandas()
        print(f"\nDataFrame shape: {df.shape}")
        print(f"DataFrame columns: {list(df.columns)}")

        if 'answer.extract_person' in df.columns:
            answer = df['answer.extract_person'].iloc[0]
            print(f"\n✓ Got answer: {answer}")
            print(f"  Type: {type(answer)}")
            if isinstance(answer, dict):
                print(f"  Name: {answer.get('name')}")
                print(f"  Age: {answer.get('age')}")
        else:
            print("\nAnswer column not found. Here's the full DataFrame:")
            print(df.head())

    except Exception as e2:
        print(f"Error converting to pandas: {e2}")

    # Method 3: Check if there were exceptions
    if hasattr(results, 'task_history'):
        print(f"\nTask history available: {len(results.task_history)} items")

except Exception as e:
    print(f"\n✗ Error occurred: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
print("Test complete")
print("="*70)
