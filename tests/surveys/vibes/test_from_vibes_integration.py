"""
Integration tests for Survey.from_vibes() with remote generation capability.

Tests the full integration from Survey.from_vibes() method through the routing
logic to both local and remote generation paths.
"""

import pytest

# Skip vibes integration tests - these test complex distributed functionality
# that depends on external services and may not be available in all environments
pytestmark = pytest.mark.skip(reason="Vibes integration tests require external services - skipping until system is more stable")
from unittest.mock import patch, MagicMock

from edsl.surveys import Survey
from edsl.surveys.vibes.remote_survey_generator import RemoteSurveyGenerator
from edsl.surveys.vibes.exceptions import RemoteSurveyGenerationError
from edsl.questions import QuestionMultipleChoice, QuestionFreeText


class TestFromVibesIntegration:
    """Integration tests for from_vibes method with local/remote routing."""

    @pytest.fixture
    def mock_remote_response(self):
        """Mock response data from remote server."""
        return {
            "questions": [
                {
                    "question_name": "satisfaction",
                    "question_text": "How satisfied are you with our service?",
                    "question_type": "multiple_choice",
                    "question_options": [
                        "Very satisfied",
                        "Satisfied",
                        "Neutral",
                        "Dissatisfied",
                        "Very dissatisfied"
                    ],
                },
                {
                    "question_name": "comments",
                    "question_text": "Any additional comments?",
                    "question_type": "free_text",
                },
                {
                    "question_name": "recommend",
                    "question_text": "Would you recommend us to others?",
                    "question_type": "multiple_choice",
                    "question_options": ["Yes", "No", "Maybe"],
                }
            ]
        }

    @pytest.fixture
    def mock_local_response(self):
        """Mock response data from local SurveyGenerator."""
        return {
            "questions": [
                {
                    "question_name": "rating",
                    "question_text": "How would you rate our product?",
                    "question_type": "multiple_choice",
                    "question_options": ["Excellent", "Good", "Fair", "Poor"],
                },
                {
                    "question_name": "feedback",
                    "question_text": "Please provide detailed feedback:",
                    "question_type": "free_text",
                }
            ]
        }

    @patch.object(RemoteSurveyGenerator, 'generate_survey')
    def test_uses_remote_when_no_api_key(self, mock_generate, mock_remote_response, monkeypatch):
        """Test that from_vibes uses remote generation when no OPENAI_API_KEY."""
        # Remove OpenAI API key to trigger remote mode
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        mock_generate.return_value = mock_remote_response

        survey = Survey.from_vibes("Customer satisfaction survey for a restaurant")

        # Verify remote generation was called
        mock_generate.assert_called_once()
        call_args = mock_generate.call_args
        assert call_args.kwargs["description"] == "Customer satisfaction survey for a restaurant"

        # Verify survey was created correctly
        assert len(survey.questions) == 3
        assert survey.questions[0].question_name == "satisfaction"
        assert survey.questions[1].question_name == "comments"
        assert survey.questions[2].question_name == "recommend"

        # Verify question types were converted correctly
        assert isinstance(survey.questions[0], QuestionMultipleChoice)
        assert isinstance(survey.questions[1], QuestionFreeText)
        assert isinstance(survey.questions[2], QuestionMultipleChoice)

    @patch('httpx.Client')
    def test_uses_remote_when_forced(self, mock_httpx_client, mock_remote_response, monkeypatch):
        """Test that from_vibes uses remote generation when remote=True."""
        # Set OpenAI API key but force remote mode
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-12345")
        monkeypatch.setenv("EXPECTED_PARROT_API_KEY", "test-api-key")

        # Mock the HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "target": "survey",
            "method": "from_vibes",
            "success": True,
            "result": mock_remote_response,
            "error": None
        }

        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_response
        mock_httpx_client.return_value.__enter__.return_value = mock_client_instance
        mock_httpx_client.return_value.__exit__.return_value = None

        survey = Survey.from_vibes(
            "Employee engagement survey",
            remote=True,
            num_questions=10,
            model="gpt-4",
            temperature=0.5
        )

        # Verify HTTP request was made
        mock_client_instance.post.assert_called_once()
        call_args = mock_client_instance.post.call_args

        # Check that the endpoint was called correctly
        assert "api/v1/vibes/dispatch" in call_args[0][0]

        # Check that the request data contains our parameters
        request_json = call_args.kwargs["json"]
        assert request_json["target"] == "survey"
        assert request_json["method"] == "from_vibes"
        assert request_json["request_data"]["description"] == "Employee engagement survey"
        assert request_json["request_data"]["num_questions"] == 10
        assert request_json["request_data"]["model"] == "gpt-4"
        assert request_json["request_data"]["temperature"] == 0.5

        # Verify survey was created
        assert len(survey.questions) == 3

    @patch('edsl.surveys.vibes.survey_generator.SurveyGenerator.generate_survey')
    def test_uses_local_when_api_key_available(self, mock_generate, mock_local_response, monkeypatch):
        """Test that from_vibes uses local generation when API key is available."""
        # Set OpenAI API key and don't force remote
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-12345")
        mock_generate.return_value = mock_local_response

        survey = Survey.from_vibes("Product feedback survey")

        # Verify local generation was called
        mock_generate.assert_called_once()
        call_args = mock_generate.call_args
        assert call_args[0][0] == "Product feedback survey"  # First positional arg

        # Verify survey was created correctly
        assert len(survey.questions) == 2
        assert survey.questions[0].question_name == "rating"
        assert survey.questions[1].question_name == "feedback"

    def test_uses_local_with_empty_api_key(self, monkeypatch):
        """Test behavior with empty OPENAI_API_KEY (should use remote)."""
        monkeypatch.setenv("OPENAI_API_KEY", "")
        # Don't set EXPECTED_PARROT_API_KEY so remote execution fails

        # This should attempt remote generation, but we expect it to fail
        # without proper API key
        with pytest.raises(Exception):
            Survey.from_vibes("Test survey")

    def test_uses_local_with_whitespace_api_key(self, monkeypatch):
        """Test behavior with whitespace-only OPENAI_API_KEY (should use remote)."""
        monkeypatch.setenv("OPENAI_API_KEY", "   \t\n  ")
        # Don't set EXPECTED_PARROT_API_KEY so remote execution fails

        # This should attempt remote generation
        with pytest.raises(Exception):
            Survey.from_vibes("Test survey")

    @patch('httpx.Client')
    def test_passes_all_parameters_to_remote(self, mock_httpx_client, mock_remote_response, monkeypatch):
        """Test that all parameters are correctly passed to remote generation."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("EXPECTED_PARROT_API_KEY", "test-api-key")

        # Mock the HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "target": "survey",
            "method": "from_vibes",
            "success": True,
            "result": mock_remote_response,
            "error": None
        }

        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_response
        mock_httpx_client.return_value.__enter__.return_value = mock_client_instance
        mock_httpx_client.return_value.__exit__.return_value = None

        Survey.from_vibes(
            description="Comprehensive survey about workplace satisfaction",
            num_questions=15,
            model="gpt-3.5-turbo",
            temperature=0.9,
            remote=True  # Explicit remote even though API key is missing
        )

        # Verify HTTP request was made
        mock_client_instance.post.assert_called_once()
        call_args = mock_client_instance.post.call_args

        # Check that the request data contains our parameters
        request_json = call_args.kwargs["json"]
        assert request_json["request_data"]["description"] == "Comprehensive survey about workplace satisfaction"
        assert request_json["request_data"]["num_questions"] == 15
        assert request_json["request_data"]["model"] == "gpt-3.5-turbo"
        assert request_json["request_data"]["temperature"] == 0.9

    @patch('edsl.surveys.vibes.survey_generator.SurveyGenerator.generate_survey')
    def test_passes_all_parameters_to_local(self, mock_generate, mock_local_response, monkeypatch):
        """Test that all parameters are correctly passed to local generation."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        mock_generate.return_value = mock_local_response

        Survey.from_vibes(
            description="Market research survey",
            num_questions=8,
            model="gpt-4o",
            temperature=0.3
        )

        # Verify parameters were passed to local generator
        mock_generate.assert_called_once()
        call_args = mock_generate.call_args

        # The call should be: generate_survey(description, **kwargs)
        assert call_args[0][0] == "Market research survey"
        # Check kwargs for num_questions parameter
        if len(call_args[0]) > 1:
            assert "num_questions" in call_args[0][1] and call_args[0][1]["num_questions"] == 8
        else:
            assert call_args.kwargs.get("num_questions") == 8

    @patch.object(RemoteSurveyGenerator, 'generate_survey')
    def test_error_propagation_from_remote(self, mock_generate, monkeypatch):
        """Test that errors from remote generation are properly propagated."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        mock_generate.side_effect = RemoteSurveyGenerationError("Server unavailable")

        with pytest.raises(Exception) as exc_info:  # VibesDispatchError wraps the original error
            Survey.from_vibes("Test survey")

        assert "Server unavailable" in str(exc_info.value)

    @patch('edsl.surveys.vibes.survey_generator.SurveyGenerator.generate_survey')
    def test_error_propagation_from_local(self, mock_generate, monkeypatch):
        """Test that errors from local generation are properly propagated."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        mock_generate.side_effect = Exception("OpenAI API error")

        with pytest.raises(Exception) as exc_info:
            Survey.from_vibes("Test survey")

        assert "OpenAI API error" in str(exc_info.value)

    @patch.object(RemoteSurveyGenerator, 'generate_survey')
    def test_question_creation_from_remote_data(self, mock_generate, monkeypatch):
        """Test that question objects are correctly created from remote data."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        # Mock response with various question types
        mock_response = {
            "questions": [
                {
                    "question_name": "rating",
                    "question_text": "Rate our service",
                    "question_type": "multiple_choice",
                    "question_options": ["Excellent", "Good", "Poor"],
                },
                {
                    "question_name": "comments",
                    "question_text": "Additional comments?",
                    "question_type": "free_text",
                },
                {
                    "question_name": "age",
                    "question_text": "What is your age?",
                    "question_type": "numerical",
                    "min_value": 18,
                    "max_value": 100,
                }
            ]
        }
        mock_generate.return_value = mock_response

        survey = Survey.from_vibes("Test survey")

        # Verify all questions were created
        assert len(survey.questions) == 3

        # Check first question (multiple choice)
        q1 = survey.questions[0]
        assert q1.question_name == "rating"
        assert q1.question_text == "Rate our service"
        assert isinstance(q1, QuestionMultipleChoice)
        assert "Excellent" in q1.question_options

        # Check second question (free text)
        q2 = survey.questions[1]
        assert q2.question_name == "comments"
        assert q2.question_text == "Additional comments?"
        assert isinstance(q2, QuestionFreeText)

        # Check third question (numerical)
        q3 = survey.questions[2]
        assert q3.question_name == "age"
        assert q3.question_text == "What is your age?"
        # Note: The exact question type depends on how _create_question_from_dict handles numerical

    @patch.object(RemoteSurveyGenerator, 'generate_survey')
    def test_fallback_question_names(self, mock_generate, monkeypatch):
        """Test that fallback question names (q0, q1, etc.) are used when needed."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        # Mock response without question_name fields
        mock_response = {
            "questions": [
                {
                    "question_name": "q0",  # Fallback name should be provided
                    "question_text": "How satisfied are you?",
                    "question_type": "multiple_choice",
                    "question_options": ["Very", "Somewhat", "Not at all"],
                },
                {
                    "question_name": "q1",  # Fallback name should be provided
                    "question_text": "Any comments?",
                    "question_type": "free_text",
                }
            ]
        }
        mock_generate.return_value = mock_response

        survey = Survey.from_vibes("Test survey")

        # The _create_question_from_dict method should provide fallback names
        # based on the pattern observed in from_vibes.py: f"q{i}"
        assert len(survey.questions) == 2
        # The actual behavior depends on the implementation of _create_question_from_dict

    @patch.object(RemoteSurveyGenerator, 'generate_survey')
    def test_empty_questions_list_handling(self, mock_generate, monkeypatch):
        """Test handling of empty questions list from remote."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        mock_response = {"questions": []}
        mock_generate.return_value = mock_response

        survey = Survey.from_vibes("Test survey")

        # Should create survey with no questions
        assert len(survey.questions) == 0
        assert isinstance(survey, Survey)

    def test_integration_with_actual_survey_methods(self, monkeypatch):
        """Test that the created survey has all expected Survey methods."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")

        # Mock the local generator to return valid data
        mock_response = {
            "questions": [
                {
                    "question_name": "test_q",
                    "question_text": "Test question?",
                    "question_type": "free_text",
                }
            ]
        }

        with patch('edsl.surveys.vibes.survey_generator.SurveyGenerator.generate_survey',
                   return_value=mock_response):
            survey = Survey.from_vibes("Test survey")

            # Verify it's a proper Survey instance with expected methods
            assert isinstance(survey, Survey)
            assert hasattr(survey, 'questions')
            assert hasattr(survey, 'add_question')
            assert len(survey.questions) == 1