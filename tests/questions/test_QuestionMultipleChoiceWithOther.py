import pytest
from edsl.questions import QuestionMultipleChoiceWithOther


class TestQuestionMultipleChoiceWithOther:
    def test_initialization(self):
        """Test that the question initializes correctly."""
        q = QuestionMultipleChoiceWithOther(
            question_name="test_question",
            question_text="Select an option",
            question_options=["Option A", "Option B", "Option C"],
            other_option_text="Other (please specify)"
        )
        
        assert q.question_name == "test_question"
        assert q.question_text == "Select an option"
        assert q.question_options == ["Option A", "Option B", "Option C"]
        assert q.other_option_text == "Other (please specify)"
        
    def test_create_response_model(self):
        """Test that the response model includes the 'Other' option."""
        q = QuestionMultipleChoiceWithOther(
            question_name="test_question",
            question_text="Select an option",
            question_options=["Option A", "Option B", "Option C"],
        )
        
        response_model = q.create_response_model()
        
        # Check that "Other" is in the valid choices for the model
        assert "Other" in response_model.model_config["json_schema_extra"]["properties"]["answer"]["enum"]
        
    def test_response_validator_valid_options(self):
        """Test that the validator accepts valid options."""
        q = QuestionMultipleChoiceWithOther(
            question_name="test_question",
            question_text="Select an option",
            question_options=["Option A", "Option B", "Option C"],
        )
        
        validator = q.response_validator
        
        # Test standard option
        result = validator.validate({"answer": "Option A"})
        assert result["answer"] == "Option A"
        
        # Test Other option with text
        result = validator.validate({"answer": "Other", "other_text": "My custom option"})
        assert result["answer"] == "Other"
        assert result["other_text"] == "My custom option"
        
        # Test Other option with comment instead of other_text
        result = validator.validate({"answer": "Other", "comment": "My custom option from comment"})
        assert result["answer"] == "Other"
        assert result["other_text"] == "My custom option from comment"
        
    def test_example_method(self):
        """Test the example class method."""
        q = QuestionMultipleChoiceWithOther.example()
        
        assert q.question_name == "how_feeling"
        assert "Good" in q.question_options
        assert hasattr(q, "other_option_text")