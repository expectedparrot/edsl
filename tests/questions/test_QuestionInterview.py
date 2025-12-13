import pytest
from edsl.questions import QuestionInterview
from edsl.questions.question_interview import InterviewResponse, InterviewResponseValidator
from polyfactory.factories.pydantic_factory import ModelFactory


class InterviewResponseFactory(ModelFactory[InterviewResponse]):
    __model__ = InterviewResponse


def test_QuestionInterview_construction():
    """Test basic construction of QuestionInterview."""
    q = QuestionInterview(
        question_name="user_experience",
        question_text="Understanding user satisfaction with our product",
        interview_guide="Ask about their experience, what they liked, what could be improved."
    )

    assert q.question_type == "interview"
    assert q.question_name == "user_experience"
    assert q.question_text == "Understanding user satisfaction with our product"
    assert q.interview_guide == "Ask about their experience, what they liked, what could be improved."


def test_QuestionInterview_construction_errors():
    """Test QuestionInterview construction with invalid parameters."""
    from edsl.questions.exceptions import QuestionInitializationError

    # Test missing required parameters
    with pytest.raises(QuestionInitializationError):
        QuestionInterview(question_name="test")  # Missing question_text and interview_guide

    with pytest.raises(QuestionInitializationError):
        QuestionInterview(
            question_name="test",
            question_text="Test question"
        )  # Missing interview_guide


def test_QuestionInterview_example():
    """Test the example method."""
    q = QuestionInterview.example()

    assert q.question_name == "customer_experience"
    assert "customer service" in q.question_text
    assert "interactions" in q.interview_guide
    assert q.question_type == "interview"


def test_QuestionInterview_example_randomized():
    """Test the example method with randomization."""
    q1 = QuestionInterview.example(randomize=True)
    q2 = QuestionInterview.example(randomize=True)

    # With randomization, the questions should be different
    assert q1.question_text != q2.question_text
    # But the base should be the same
    assert "customer service" in q1.question_text
    assert "customer service" in q2.question_text


def test_QuestionInterview_response_model():
    """Test the InterviewResponse model."""
    # Test valid response
    response = InterviewResponse(answer="Interviewer: How are you?\nRespondent: I'm good!")
    assert response.answer == "Interviewer: How are you?\nRespondent: I'm good!"
    assert response.generated_tokens is None

    # Test with generated tokens
    response_with_tokens = InterviewResponse(
        answer="Interviewer: Hello\nRespondent: Hi",
        generated_tokens="Interviewer: Hello\nRespondent: Hi"
    )
    assert response_with_tokens.answer == response_with_tokens.generated_tokens

    # Test field validation - non-string answer should be converted
    response_numeric = InterviewResponse(answer=123)
    assert response_numeric.answer == "123"


def test_QuestionInterview_response_validation():
    """Test response validation with mismatched tokens."""
    from edsl.questions.exceptions import QuestionAnswerValidationError

    # Test mismatched answer and generated_tokens
    with pytest.raises(QuestionAnswerValidationError):
        InterviewResponse(
            answer="Interviewer: How are you?\nRespondent: Fine",
            generated_tokens="Different content"
        )


def test_QuestionInterview_validator():
    """Test the InterviewResponseValidator."""
    q = QuestionInterview(
        question_name="test",
        question_text="Test question",
        interview_guide="Test guide"
    )

    validator = q.response_validator
    assert isinstance(validator, InterviewResponseValidator)

    # Test valid response
    valid_response = {
        "answer": "Interviewer: Test question?\nRespondent: Test answer."
    }
    validated = validator.validate(valid_response)
    assert validated["answer"] == "Interviewer: Test question?\nRespondent: Test answer."

    # Test fixing None response
    invalid_response = {"answer": None}
    validated = validator.validate(invalid_response)
    assert validated["answer"] == ""

    # Test fixing with matching generated tokens
    response_with_matching_tokens = {
        "answer": "Interviewer: Right question?\nRespondent: Right answer.",
        "generated_tokens": "Interviewer: Right question?\nRespondent: Right answer."
    }
    validated = validator.validate(response_with_matching_tokens)
    assert validated["answer"] == "Interviewer: Right question?\nRespondent: Right answer."
    assert validated["generated_tokens"] == "Interviewer: Right question?\nRespondent: Right answer."

    # Test the fix method directly for mismatched tokens
    fix_response = validator.fix({
        "answer": "Wrong answer",
        "generated_tokens": "Interviewer: Right question?\nRespondent: Right answer."
    })
    assert fix_response["answer"] == "Interviewer: Right question?\nRespondent: Right answer."


def test_QuestionInterview_html_content():
    """Test HTML content generation."""
    q = QuestionInterview(
        question_name="feedback_interview",
        question_text="Understanding customer feedback",
        interview_guide="Ask about satisfaction, issues, and suggestions"
    )

    html = q.question_html_content
    assert "Research Question:" in html
    assert "Interview Guide:" in html
    assert "Interview Transcript:" in html
    assert "feedback_interview" in html
    assert "Understanding customer feedback" in html
    assert "satisfaction, issues, and suggestions" in html


def test_QuestionInterview_serialization():
    """Test serialization and deserialization."""
    q = QuestionInterview(
        question_name="survey_interview",
        question_text="Research question about user behavior",
        interview_guide="Focus on daily habits and preferences"
    )

    # Test serialization
    serialized = q.to_dict()
    assert serialized["question_name"] == "survey_interview"
    assert serialized["question_text"] == "Research question about user behavior"
    assert serialized["interview_guide"] == "Focus on daily habits and preferences"
    assert serialized["question_type"] == "interview"

    # Test deserialization
    from edsl.questions import QuestionBase
    deserialized = QuestionBase.from_dict(serialized)
    assert isinstance(deserialized, QuestionInterview)
    assert deserialized.question_name == q.question_name
    assert deserialized.question_text == q.question_text
    assert deserialized.interview_guide == q.interview_guide


def test_QuestionInterview_question_type():
    """Test question type identifier."""
    q = QuestionInterview.example()
    assert q.question_type == "interview"


def test_QuestionInterview_simulation():
    """Test answer simulation."""
    q = QuestionInterview.example()

    # Test _simulate_answer method exists and returns dict
    simulated = q._simulate_answer()
    assert isinstance(simulated, dict)
    assert "answer" in simulated
    assert isinstance(simulated["answer"], str)


def test_QuestionInterview_templates():
    """Test template rendering."""
    q = QuestionInterview(
        question_name="template_test",
        question_text="Test research question",
        interview_guide="Test interview guide with specific instructions"
    )

    # Test question presentation template
    presentation = q.question_presentation.text
    assert "{{question_text}}" in presentation
    assert "{{interview_guide}}" in presentation
    assert "Interview Guide" in presentation

    # Test answering instructions template
    instructions = q.answering_instructions.text
    assert "You are the respondent" in instructions
    assert "Interviewer:" in instructions
    assert "Respondent:" in instructions
    assert "dialogue" in instructions


def test_QuestionInterview_fake_data():
    """Test fake data generation for testing."""
    q = QuestionInterview.example()

    # Test that we can generate fake responses using the question's factory
    fake_response = q.fake_data_factory.build()
    assert hasattr(fake_response, 'answer')
    assert isinstance(fake_response.answer, str)

    # Test validation of fake response
    validated = q._validate_answer(fake_response.model_dump())
    assert isinstance(validated, dict)
    assert "answer" in validated


def test_QuestionInterview_validator_examples():
    """Test validator examples for testing purposes."""
    # Test class-level examples without instantiation
    assert len(InterviewResponseValidator.valid_examples) > 0
    valid_example = InterviewResponseValidator.valid_examples[0]
    response_dict, params = valid_example
    assert "answer" in response_dict
    assert "Interviewer:" in response_dict["answer"]
    assert "Respondent:" in response_dict["answer"]

    # Test invalid examples
    assert len(InterviewResponseValidator.invalid_examples) > 0
    invalid_example = InterviewResponseValidator.invalid_examples[0]
    response_dict, params, expected_error = invalid_example
    assert response_dict["answer"] is None


if __name__ == "__main__":
    pytest.main([__file__])