"""
Live test of QuestionPydantic with OpenAI API
"""

from pydantic import BaseModel, Field
from edsl.questions import QuestionPydantic
from edsl.language_models import Model


class Person(BaseModel):
    """A model representing a person's information."""
    name: str = Field(description="Full name of the person")
    age: int = Field(description="Age in years", ge=0, le=150)
    occupation: str = Field(description="Job title or profession")


class Book(BaseModel):
    """A model representing a book."""
    title: str = Field(description="Title of the book")
    author: str = Field(description="Author's name")
    year: int = Field(description="Publication year", ge=1000, le=2100)
    genre: str = Field(description="Literary genre")


def test_person_extraction():
    """Test extracting person information from text."""
    print("=" * 70)
    print("Test 1: Person Information Extraction")
    print("=" * 70)

    q = QuestionPydantic(
        question_name="extract_person",
        question_text="""Extract information about the person from this text:

        Dr. Sarah Chen is a 42-year-old neuroscientist working at Stanford University.

        Provide the extracted information.""",
        pydantic_model=Person
    )

    print(f"\nQuestion: {q.question_text}")
    print(f"\nExpected schema: {q.user_pydantic_model.__name__}")

    # Use GPT-4 mini for testing
    m = Model("gpt-4o-mini")

    print("\nRunning with gpt-4o-mini...")
    try:
        results = q.by(m).run()
        answer = results.select("answer.extract_person").first()
        print(f"\n✓ Success! Got answer: {answer}")
        print(f"  Name: {answer.get('name')}")
        print(f"  Age: {answer.get('age')}")
        print(f"  Occupation: {answer.get('occupation')}")
        return True
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_book_extraction():
    """Test extracting book information from text."""
    print("\n" + "=" * 70)
    print("Test 2: Book Information Extraction")
    print("=" * 70)

    q = QuestionPydantic(
        question_name="extract_book",
        question_text="""Extract information about the book from this text:

        '1984' by George Orwell, published in 1949, is a dystopian fiction novel.

        Provide the extracted information.""",
        pydantic_model=Book
    )

    print(f"\nQuestion: {q.question_text}")
    print(f"\nExpected schema: {q.user_pydantic_model.__name__}")

    m = Model("gpt-4o-mini")

    print("\nRunning with gpt-4o-mini...")
    try:
        results = q.by(m).run()
        answer = results.select("answer.extract_book").first()
        print(f"\n✓ Success! Got answer: {answer}")
        print(f"  Title: {answer.get('title')}")
        print(f"  Author: {answer.get('author')}")
        print(f"  Year: {answer.get('year')}")
        print(f"  Genre: {answer.get('genre')}")
        return True
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_multiple_questions():
    """Test running multiple QuestionPydantic questions in a survey."""
    print("\n" + "=" * 70)
    print("Test 3: Multiple Questions in Survey")
    print("=" * 70)

    from edsl import Survey

    q1 = QuestionPydantic(
        question_name="person1",
        question_text="Extract: Alice Johnson is a 28-year-old software developer.",
        pydantic_model=Person
    )

    q2 = QuestionPydantic(
        question_name="person2",
        question_text="Extract: Bob Smith is a 55-year-old professor.",
        pydantic_model=Person
    )

    survey = Survey(questions=[q1, q2])
    m = Model("gpt-4o-mini")

    print("\nRunning survey with 2 QuestionPydantic questions...")
    try:
        results = survey.by(m).run()
        answer1 = results.select("answer.person1").first()
        answer2 = results.select("answer.person2").first()

        print(f"\n✓ Success! Got both answers:")
        print(f"  Person 1: {answer1}")
        print(f"  Person 2: {answer2}")
        return True
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("QuestionPydantic Live API Tests")
    print("=" * 70)
    print("\nTesting QuestionPydantic with OpenAI's API to verify:")
    print("1. JSON schema is correctly passed to the API")
    print("2. Structured output is properly generated")
    print("3. Responses validate against the Pydantic models")
    print("=" * 70 + "\n")

    results = []

    # Run tests
    results.append(("Person Extraction", test_person_extraction()))
    results.append(("Book Extraction", test_book_extraction()))
    results.append(("Multiple Questions", test_multiple_questions()))

    # Summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)

    for name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{status}: {name}")

    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\nTotal: {passed}/{total} tests passed")
    print("=" * 70 + "\n")
