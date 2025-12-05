"""
Unit tests for remote survey generation client.

Tests the RemoteSurveyGenerator class and should_use_remote function
using mock patterns consistent with EDSL testing approaches.
"""

import pytest
from unittest.mock import patch, Mock, PropertyMock
import requests
import os

from edsl.surveys.vibes.remote_survey_generator import (
    RemoteSurveyGenerator,
    should_use_remote,
)
from edsl.surveys.vibes.exceptions import (
    RemoteSurveyGenerationError,
    SurveyGenerationError,
)


class TestShouldUseRemote:
    """Tests for should_use_remote function."""

    def test_force_remote_true(self, monkeypatch):
        """Test that force_remote=True always returns True."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        assert should_use_remote(force_remote=True) is True

    def test_no_api_key(self, monkeypatch):
        """Test that missing API key returns True."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        assert should_use_remote(force_remote=False) is True

    def test_empty_api_key(self, monkeypatch):
        """Test that empty API key returns True."""
        monkeypatch.setenv("OPENAI_API_KEY", "")
        assert should_use_remote(force_remote=False) is True

    def test_whitespace_only_api_key(self, monkeypatch):
        """Test that whitespace-only API key returns True."""
        monkeypatch.setenv("OPENAI_API_KEY", "   ")
        assert should_use_remote(force_remote=False) is True

    def test_has_valid_api_key(self, monkeypatch):
        """Test that having valid API key returns False."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        assert should_use_remote(force_remote=False) is False

    def test_force_remote_overrides_key(self, monkeypatch):
        """Test that force_remote=True overrides having API key."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        assert should_use_remote(force_remote=True) is True


class TestRemoteSurveyGenerator:
    """Tests for RemoteSurveyGenerator class."""

    @pytest.fixture
    def mock_key_handler(self):
        """Mock the ExpectedParrotKeyHandler."""
        with patch('edsl.surveys.vibes.remote_survey_generator.ExpectedParrotKeyHandler') as mock:
            mock_instance = Mock()
            mock_instance.get_ep_api_key.return_value = "test-ep-key"
            mock.return_value = mock_instance
            yield mock_instance

    @pytest.fixture
    def generator(self, mock_key_handler):
        """Create a RemoteSurveyGenerator instance with mocked key handler."""
        return RemoteSurveyGenerator(base_url="http://localhost:8000/api/v1/surveys")

    @pytest.fixture
    def mock_successful_response(self):
        """Create a mock successful response."""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "questions": [
                {
                    "question_name": "brand_awareness",
                    "question_text": "How familiar are you with our brand?",
                    "question_type": "multiple_choice",
                    "question_options": ["Very familiar", "Somewhat familiar", "Not familiar"],
                },
                {
                    "question_name": "satisfaction",
                    "question_text": "How satisfied are you?",
                    "question_type": "likert_five",
                }
            ]
        }
        return mock_resp

    def test_initialization_default_url(self, mock_key_handler):
        """Test initialization with default URL."""
        generator = RemoteSurveyGenerator()
        assert "localhost:8000" in generator.base_url
        assert "/api/v1/surveys" in generator.base_url

    def test_initialization_custom_url(self, mock_key_handler):
        """Test initialization with custom URL."""
        custom_url = "http://custom.example.com/api/surveys"
        generator = RemoteSurveyGenerator(base_url=custom_url)
        assert generator.base_url == custom_url

    def test_initialization_with_env_var(self, mock_key_handler, monkeypatch):
        """Test initialization uses environment variable."""
        test_url = "http://env.example.com/surveys"
        monkeypatch.setenv("EDSL_SURVEY_GENERATION_URL", test_url)
        generator = RemoteSurveyGenerator()
        assert generator.base_url == test_url

    def test_initialization_strips_trailing_slash(self, mock_key_handler):
        """Test that trailing slash is stripped from base URL."""
        generator = RemoteSurveyGenerator(base_url="http://example.com/api/")
        assert generator.base_url == "http://example.com/api"

    def test_headers_with_valid_key(self, generator):
        """Test that headers are properly formed with valid key."""
        headers = generator.headers
        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "application/json"
        assert headers["Authorization"] == "Bearer test-ep-key"
        assert "X-Request-ID" in headers

    def test_headers_with_missing_key(self, monkeypatch):
        """Test that missing Expected Parrot key raises error."""
        with patch('edsl.surveys.vibes.remote_survey_generator.ExpectedParrotKeyHandler') as mock:
            mock_instance = Mock()
            mock_instance.get_ep_api_key.return_value = None
            mock.return_value = mock_instance

            generator = RemoteSurveyGenerator()
            with pytest.raises(RemoteSurveyGenerationError) as exc_info:
                _ = generator.headers

            assert "EXPECTED_PARROT_API_KEY is required" in str(exc_info.value)

    def test_headers_with_key_handler_exception(self, monkeypatch):
        """Test that key handler exception is properly handled."""
        with patch('edsl.surveys.vibes.remote_survey_generator.ExpectedParrotKeyHandler') as mock:
            mock_instance = Mock()
            mock_instance.get_ep_api_key.side_effect = Exception("Key retrieval failed")
            mock.return_value = mock_instance

            generator = RemoteSurveyGenerator()
            with pytest.raises(RemoteSurveyGenerationError) as exc_info:
                _ = generator.headers

            assert "Failed to get Expected Parrot API key" in str(exc_info.value)

    @patch('requests.post')
    def test_generate_survey_success(self, mock_post, generator, mock_successful_response):
        """Test successful survey generation."""
        mock_post.return_value = mock_successful_response

        result = generator.generate_survey(
            description="Test survey about customer satisfaction",
            num_questions=5,
            model="gpt-4o",
            temperature=0.7
        )

        # Verify the result structure
        assert "questions" in result
        assert len(result["questions"]) == 2
        assert result["questions"][0]["question_name"] == "brand_awareness"
        assert result["questions"][1]["question_type"] == "likert_five"

        # Verify the request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Check URL
        assert call_args[1]["json"]["description"] == "Test survey about customer satisfaction"
        assert call_args[1]["json"]["num_questions"] == 5
        assert call_args[1]["json"]["model"] == "gpt-4o"
        assert call_args[1]["json"]["temperature"] == 0.7

        # Check headers
        assert "Authorization" in call_args[1]["headers"]
        assert "Bearer test-ep-key" in call_args[1]["headers"]["Authorization"]

    @patch('requests.post')
    def test_generate_survey_optional_num_questions(self, mock_post, generator, mock_successful_response):
        """Test survey generation without specifying num_questions."""
        mock_post.return_value = mock_successful_response

        result = generator.generate_survey(description="Test survey")

        # Verify num_questions is not included in request when None
        call_args = mock_post.call_args
        assert "num_questions" not in call_args[1]["json"]

        # But other defaults should be present
        assert call_args[1]["json"]["model"] == "gpt-4o"
        assert call_args[1]["json"]["temperature"] == 0.7

    @patch('requests.post')
    def test_generate_survey_auth_error(self, mock_post, generator):
        """Test handling of authentication errors (401)."""
        mock_resp = Mock()
        mock_resp.status_code = 401
        mock_resp.json.return_value = {"detail": "Invalid API key"}
        mock_post.return_value = mock_resp

        with pytest.raises(RemoteSurveyGenerationError) as exc_info:
            generator.generate_survey(description="Test survey")

        assert "Authentication failed" in str(exc_info.value)
        assert "EXPECTED_PARROT_API_KEY" in str(exc_info.value)

    @patch('requests.post')
    def test_generate_survey_validation_error(self, mock_post, generator):
        """Test handling of validation errors (422)."""
        mock_resp = Mock()
        mock_resp.status_code = 422
        mock_resp.json.return_value = {
            "detail": [
                {"field": "description", "message": "Field required"}
            ]
        }
        mock_post.return_value = mock_resp

        with pytest.raises(SurveyGenerationError) as exc_info:
            generator.generate_survey(description="")

        assert "Invalid request parameters" in str(exc_info.value)

    @patch('requests.post')
    def test_generate_survey_server_error(self, mock_post, generator):
        """Test handling of server errors (500)."""
        mock_resp = Mock()
        mock_resp.status_code = 500
        mock_resp.json.return_value = {"detail": "OpenAI API error"}
        mock_post.return_value = mock_resp

        with pytest.raises(SurveyGenerationError) as exc_info:
            generator.generate_survey(description="Test survey")

        assert "Survey generation failed on server" in str(exc_info.value)

    @patch('requests.post')
    def test_generate_survey_other_http_error(self, mock_post, generator):
        """Test handling of other HTTP errors."""
        mock_resp = Mock()
        mock_resp.status_code = 503
        mock_resp.json.return_value = {"detail": "Service temporarily unavailable"}
        mock_post.return_value = mock_resp

        with pytest.raises(RemoteSurveyGenerationError) as exc_info:
            generator.generate_survey(description="Test survey")

        assert "503" in str(exc_info.value)
        assert "Service temporarily unavailable" in str(exc_info.value)

    @patch('requests.post')
    def test_generate_survey_connection_error(self, mock_post, generator):
        """Test handling of connection errors."""
        mock_post.side_effect = requests.ConnectionError("Cannot connect to server")

        with pytest.raises(requests.ConnectionError) as exc_info:
            generator.generate_survey(description="Test survey")

        assert "Could not connect" in str(exc_info.value)

    @patch('requests.post')
    def test_generate_survey_timeout(self, mock_post, generator):
        """Test handling of timeout errors."""
        mock_post.side_effect = requests.Timeout("Request timed out")

        with pytest.raises(requests.Timeout) as exc_info:
            generator.generate_survey(description="Test survey")

        assert "timed out" in str(exc_info.value).lower()

    @patch('requests.post')
    def test_generate_survey_invalid_response_structure(self, mock_post, generator):
        """Test handling of invalid response structure."""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"invalid": "response"}
        mock_post.return_value = mock_resp

        with pytest.raises(RemoteSurveyGenerationError) as exc_info:
            generator.generate_survey(description="Test survey")

        assert "missing 'questions' key" in str(exc_info.value).lower()

    @patch('requests.post')
    def test_generate_survey_non_list_questions(self, mock_post, generator):
        """Test handling of non-list questions field."""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"questions": "not a list"}
        mock_post.return_value = mock_resp

        with pytest.raises(RemoteSurveyGenerationError) as exc_info:
            generator.generate_survey(description="Test survey")

        assert "'questions' must be a list" in str(exc_info.value)

    @patch('requests.post')
    def test_generate_survey_invalid_question_structure(self, mock_post, generator):
        """Test handling of invalid question structure."""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "questions": [
                {"question_name": "q1", "question_text": "What?"},  # Missing question_type
            ]
        }
        mock_post.return_value = mock_resp

        with pytest.raises(RemoteSurveyGenerationError) as exc_info:
            generator.generate_survey(description="Test survey")

        assert "missing 'question_type' field" in str(exc_info.value)

    @patch('requests.post')
    def test_generate_survey_json_decode_error(self, mock_post, generator):
        """Test handling of JSON decode errors."""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.side_effect = ValueError("Invalid JSON")
        mock_resp.text = "Invalid JSON response"
        mock_post.return_value = mock_resp

        with pytest.raises(RemoteSurveyGenerationError) as exc_info:
            generator.generate_survey(description="Test survey")

        assert "invalid json response" in str(exc_info.value).lower()

    @patch('requests.post')
    def test_extract_error_detail_with_json(self, mock_post, generator):
        """Test error detail extraction from JSON response."""
        mock_resp = Mock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {"detail": "Custom error message"}
        mock_post.return_value = mock_resp

        with pytest.raises(RemoteSurveyGenerationError) as exc_info:
            generator.generate_survey(description="Test survey")

        assert "Custom error message" in str(exc_info.value)

    @patch('requests.post')
    def test_extract_error_detail_fallback_to_text(self, mock_post, generator):
        """Test error detail extraction falls back to response text."""
        mock_resp = Mock()
        mock_resp.status_code = 400
        mock_resp.json.side_effect = ValueError("Invalid JSON")
        mock_resp.text = "Raw error message"
        mock_post.return_value = mock_resp

        with pytest.raises(RemoteSurveyGenerationError) as exc_info:
            generator.generate_survey(description="Test survey")

        assert "Raw error message" in str(exc_info.value)

    @patch('requests.get')
    def test_health_check_success(self, mock_get, generator):
        """Test successful health check."""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        result = generator.health_check()
        assert result is True

    @patch('requests.get')
    def test_health_check_404_ok(self, mock_get, generator):
        """Test health check treats 404 as OK (server is up)."""
        mock_resp = Mock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp

        result = generator.health_check()
        assert result is True

    @patch('requests.get')
    def test_health_check_connection_error(self, mock_get, generator):
        """Test health check handles connection errors."""
        mock_get.side_effect = requests.ConnectionError("Cannot connect")

        result = generator.health_check()
        assert result is False

    @patch('requests.get')
    def test_health_check_timeout(self, mock_get, generator):
        """Test health check handles timeouts."""
        mock_get.side_effect = requests.Timeout("Timeout")

        result = generator.health_check()
        assert result is False

    @patch('requests.get')
    def test_health_check_server_error(self, mock_get, generator):
        """Test health check handles server errors."""
        mock_resp = Mock()
        mock_resp.status_code = 500
        mock_get.return_value = mock_resp

        result = generator.health_check()
        assert result is False

    def test_custom_timeout(self, generator, mock_successful_response):
        """Test that custom timeout is passed to requests."""
        with patch('requests.post', return_value=mock_successful_response) as mock_post:
            generator.generate_survey(
                description="Test survey",
                timeout=120
            )

            # Verify timeout was passed
            call_args = mock_post.call_args
            assert call_args[1]["timeout"] == 120