from pydantic import BaseModel, Field
from edsl.questions import QuestionPydantic
from edsl.language_models import Model

class Person(BaseModel):
    name: str = Field(description="Full name")
    age: int = Field(description="Age", ge=0, le=150)
    occupation: str

q = QuestionPydantic(
    question_name="extract_person",
    question_text="Extract: Alice Johnson is a 28-year-old software engineer",
    pydantic_model=Person
)

results = q.by(Model('gpt-4o-mini')).run()