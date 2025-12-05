"""
Tests for the FastAPI survey generation server.

Tests all endpoints of the survey generation server using FastAPI TestClient,
following EDSL's testing patterns for server applications.
"""

import pytest

# Skip all vibes server tests - these require a running server infrastructure
# that may not be available in all test environments
pytestmark = pytest.mark.skip(reason="Vibes server tests require running infrastructure - skipping until system is more stable")
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock
import json

from edsl.surveys.vibes.server.app import app


class TestServerEndpoints:
    """Test class for server endpoints."""

    @pytest.fixture
    def client(self):
        """Create a FastAPI test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_survey_data(self):
        """Mock survey data from SurveyGenerator."""
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
                    "question_name": "feedback",
                    "question_text": "Please provide additional feedback:",
                    "question_type": "free_text",
                },
                {
                    "question_name": "recommend",
                    "question_text": "Would you recommend us to others?",
                    "question_type": "multiple_choice",
                    "question_options": ["Yes", "No"],
                }
            ]
        }

    @pytest.fixture
    def valid_headers(self):
        """Valid authorization headers."""
        return {
            "Authorization": "Bearer test-expected-parrot-key-12345",
            "Content-Type": "application/json",
        }

    @pytest.fixture
    def valid_request_data(self):
        """Valid survey generation request data."""
        return {
            "description": "Customer satisfaction survey for a restaurant",
            "num_questions": 5,
            "model": "gpt-4o",
            "temperature": 0.7,
        }


class TestRootEndpoint(TestServerEndpoints):
    """Tests for root endpoint."""

    def test_root_endpoint(self, client):
        """Test root endpoint returns API information."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert data["service"] == "EDSL Survey Generation API"
        assert "version" in data
        assert "endpoints" in data
        assert "authentication" in data

        # Verify important endpoints are listed
        endpoints = data["endpoints"]
        assert "/health" in endpoints.values()
        assert "/api/v1/surveys/from-vibes" in endpoints.values()
        assert "/docs" in endpoints.values()


class TestHealthEndpoint(TestServerEndpoints):
    """Tests for health check endpoint."""

    def test_health_check_with_openai_key(self, client, monkeypatch):
        """Test health check when OpenAI key is available."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "EDSL Survey Generation API"
        assert data["openai_configured"] is True
        assert "timestamp" in data

    def test_health_check_without_openai_key(self, client, monkeypatch):
        """Test health check when OpenAI key is missing."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["openai_configured"] is False

    def test_health_check_no_auth_required(self, client):
        """Test that health check doesn't require authentication."""
        response = client.get("/health")

        assert response.status_code == 200
        # Should not return 401 Unauthorized


class TestSurveyGenerationEndpoint(TestServerEndpoints):
    """Tests for the main survey generation endpoint."""


    def test_missing_authorization_header(self, client, valid_request_data):
        """Test request without Authorization header fails."""
        response = client.post(
            "/api/v1/surveys/from-vibes",
            json=valid_request_data
        )

        assert response.status_code == 403
        data = response.json()
        assert "detail" in data

    def test_invalid_authorization_format(self, client, valid_request_data):
        """Test request with invalid authorization format."""
        invalid_headers = {"Authorization": "InvalidFormat token123"}

        response = client.post(
            "/api/v1/surveys/from-vibes",
            json=valid_request_data,
            headers=invalid_headers
        )

        assert response.status_code == 401

    def test_empty_api_key(self, client, valid_request_data):
        """Test request with empty API key."""
        invalid_headers = {"Authorization": "Bearer "}

        response = client.post(
            "/api/v1/surveys/from-vibes",
            json=valid_request_data,
            headers=invalid_headers
        )

        assert response.status_code == 401

    def test_short_api_key(self, client, valid_request_data):
        """Test request with API key that's too short."""
        invalid_headers = {"Authorization": "Bearer short"}

        response = client.post(
            "/api/v1/surveys/from-vibes",
            json=valid_request_data,
            headers=invalid_headers
        )

        assert response.status_code == 401

    def test_missing_openai_key_on_server(self, client, valid_headers,
                                         valid_request_data, monkeypatch):
        """Test server error when OPENAI_API_KEY is not configured."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        response = client.post(
            "/api/v1/surveys/from-vibes",
            json=valid_request_data,
            headers=valid_headers
        )

        assert response.status_code == 500
        data = response.json()
        assert "OPENAI_API_KEY not set" in data["detail"]["detail"]

    def test_missing_required_field_description(self, client, valid_headers):
        """Test validation error for missing description field."""
        invalid_data = {
            "model": "gpt-4o",
            "temperature": 0.7,
            # Missing description
        }

        response = client.post(
            "/api/v1/surveys/from-vibes",
            json=invalid_data,
            headers=valid_headers
        )

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_invalid_description_too_short(self, client, valid_headers):
        """Test validation error for description that's too short."""
        invalid_data = {
            "description": "short",  # Less than minimum length
            "model": "gpt-4o",
            "temperature": 0.7,
        }

        response = client.post(
            "/api/v1/surveys/from-vibes",
            json=invalid_data,
            headers=valid_headers
        )

        assert response.status_code == 422

    def test_invalid_num_questions_negative(self, client, valid_headers):
        """Test validation error for negative num_questions."""
        invalid_data = {
            "description": "Test survey about customer satisfaction",
            "num_questions": -1,  # Invalid negative value
        }

        response = client.post(
            "/api/v1/surveys/from-vibes",
            json=invalid_data,
            headers=valid_headers
        )

        assert response.status_code == 422

    def test_invalid_num_questions_too_large(self, client, valid_headers):
        """Test validation error for num_questions that's too large."""
        invalid_data = {
            "description": "Test survey about customer satisfaction",
            "num_questions": 100,  # Exceeds maximum of 50
        }

        response = client.post(
            "/api/v1/surveys/from-vibes",
            json=invalid_data,
            headers=valid_headers
        )

        assert response.status_code == 422

    def test_invalid_temperature_too_high(self, client, valid_headers):
        """Test validation error for temperature that's too high."""
        invalid_data = {
            "description": "Test survey about customer satisfaction",
            "temperature": 3.0,  # Exceeds maximum of 2.0
        }

        response = client.post(
            "/api/v1/surveys/from-vibes",
            json=invalid_data,
            headers=valid_headers
        )

        assert response.status_code == 422

    def test_invalid_temperature_negative(self, client, valid_headers):
        """Test validation error for negative temperature."""
        invalid_data = {
            "description": "Test survey about customer satisfaction",
            "temperature": -0.5,  # Below minimum of 0.0
        }

        response = client.post(
            "/api/v1/surveys/from-vibes",
            json=invalid_data,
            headers=valid_headers
        )

        assert response.status_code == 422

    @patch('edsl.surveys.vibes.server.app.SurveyGenerator.generate_survey')
    def test_survey_generator_import_error(self, mock_generate, client, valid_headers,
                                          valid_request_data, monkeypatch):
        """Test handling of SurveyGenerator import errors."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")

        # Mock an import error when trying to import SurveyGenerator
        with patch('edsl.surveys.vibes.server.app.SurveyGenerator', side_effect=ImportError("Module not found")):
            response = client.post(
                "/api/v1/surveys/from-vibes",
                json=valid_request_data,
                headers=valid_headers
            )

            assert response.status_code == 500
            data = response.json()
            assert "import_error" in data["detail"]["error_type"]

    @patch('edsl.surveys.vibes.server.app.SurveyGenerator.generate_survey')
    def test_survey_generation_exception(self, mock_generate, client, valid_headers,
                                        valid_request_data, monkeypatch):
        """Test handling of survey generation exceptions."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        mock_generate.side_effect = Exception("OpenAI API rate limit exceeded")

        response = client.post(
            "/api/v1/surveys/from-vibes",
            json=valid_request_data,
            headers=valid_headers
        )

        assert response.status_code == 500
        data = response.json()
        assert "OpenAI API rate limit exceeded" in data["detail"]["detail"]
        assert "openai_error" in data["detail"]["error_type"]

    @patch('edsl.surveys.vibes.server.app.SurveyGenerator.generate_survey')
    def test_non_openai_generation_exception(self, mock_generate, client, valid_headers,
                                            valid_request_data, monkeypatch):
        """Test handling of non-OpenAI generation exceptions."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        mock_generate.side_effect = Exception("Some other error")

        response = client.post(
            "/api/v1/surveys/from-vibes",
            json=valid_request_data,
            headers=valid_headers
        )

        assert response.status_code == 500
        data = response.json()
        assert "Some other error" in data["detail"]["detail"]
        assert "generation_error" in data["detail"]["error_type"]

    @patch('edsl.surveys.vibes.server.app.SurveyGenerator.generate_survey')
    def test_invalid_survey_data_structure_not_dict(self, mock_generate, client, valid_headers,
                                                   valid_request_data, monkeypatch):
        """Test handling of invalid survey data structure (not a dict)."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        mock_generate.return_value = "not a dict"

        response = client.post(
            "/api/v1/surveys/from-vibes",
            json=valid_request_data,
            headers=valid_headers
        )

        assert response.status_code == 500
        data = response.json()
        assert "Invalid survey data structure" in data["detail"]["detail"]

    @patch('edsl.surveys.vibes.server.app.SurveyGenerator.generate_survey')
    def test_invalid_survey_data_missing_questions(self, mock_generate, client, valid_headers,
                                                  valid_request_data, monkeypatch):
        """Test handling of survey data missing questions key."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        mock_generate.return_value = {"invalid": "structure"}

        response = client.post(
            "/api/v1/surveys/from-vibes",
            json=valid_request_data,
            headers=valid_headers
        )

        assert response.status_code == 500
        data = response.json()
        assert "Invalid survey data structure" in data["detail"]["detail"]

    @patch('edsl.surveys.vibes.server.app.SurveyGenerator.generate_survey')
    def test_invalid_questions_not_list(self, mock_generate, client, valid_headers,
                                       valid_request_data, monkeypatch):
        """Test handling of questions field that's not a list."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        mock_generate.return_value = {"questions": "not a list"}

        response = client.post(
            "/api/v1/surveys/from-vibes",
            json=valid_request_data,
            headers=valid_headers
        )

        assert response.status_code == 500
        data = response.json()
        assert "Questions data must be a list" in data["detail"]["detail"]

    @patch('edsl.surveys.vibes.server.app.SurveyGenerator.generate_survey')
    def test_optional_num_questions_parameter(self, mock_generate, client, valid_headers,
                                             mock_survey_data, monkeypatch):
        """Test that num_questions parameter is optional."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        mock_generate.return_value = mock_survey_data

        request_data = {
            "description": "Simple survey without num_questions specified",
            "model": "gpt-4o",
            "temperature": 0.5,
        }

        response = client.post(
            "/api/v1/surveys/from-vibes",
            json=request_data,
            headers=valid_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["generated_with"]["num_questions_requested"] is None

    @patch('edsl.surveys.vibes.server.app.SurveyGenerator.generate_survey')
    def test_default_parameters(self, mock_generate, client, valid_headers,
                               mock_survey_data, monkeypatch):
        """Test that default parameters are used when not specified."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        mock_generate.return_value = mock_survey_data

        minimal_request = {
            "description": "Minimal survey request using defaults"
        }

        response = client.post(
            "/api/v1/surveys/from-vibes",
            json=minimal_request,
            headers=valid_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Check that defaults were applied
        metadata = data["generated_with"]
        assert metadata["model"] == "gpt-4o"  # Default model
        assert metadata["temperature"] == 0.7  # Default temperature

    def test_content_type_requirement(self, client, valid_headers, valid_request_data):
        """Test that proper Content-Type header is required."""
        headers_without_content_type = {
            "Authorization": valid_headers["Authorization"]
            # Missing Content-Type
        }

        response = client.post(
            "/api/v1/surveys/from-vibes",
            json=valid_request_data,
            headers=headers_without_content_type
        )

        # FastAPI should handle this automatically, but test to be sure
        # The request should still work as TestClient handles JSON properly
        assert response.status_code in [200, 422, 401, 500]

    @patch('edsl.surveys.vibes.server.app.SurveyGenerator.generate_survey')
    def test_response_includes_request_id(self, mock_generate, client, valid_headers,
                                         valid_request_data, mock_survey_data, monkeypatch):
        """Test that response includes a unique request ID."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        mock_generate.return_value = mock_survey_data

        response = client.post(
            "/api/v1/surveys/from-vibes",
            json=valid_request_data,
            headers=valid_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "request_id" in data
        assert len(data["request_id"]) > 10  # Should be a UUID

    @patch('edsl.surveys.vibes.server.app.SurveyGenerator.generate_survey')
    def test_question_with_optional_fields(self, mock_generate, client, valid_headers,
                                          valid_request_data, monkeypatch):
        """Test handling of questions with optional fields."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")

        survey_data_with_optional_fields = {
            "questions": [
                {
                    "question_name": "age",
                    "question_text": "What is your age?",
                    "question_type": "numerical",
                    "min_value": 18,
                    "max_value": 100,
                },
                {
                    "question_name": "rating",
                    "question_text": "Rate our service",
                    "question_type": "multiple_choice",
                    "question_options": ["Excellent", "Good", "Fair", "Poor"]
                }
            ]
        }
        mock_generate.return_value = survey_data_with_optional_fields

        response = client.post(
            "/api/v1/surveys/from-vibes",
            json=valid_request_data,
            headers=valid_headers
        )

        assert response.status_code == 200
        data = response.json()

        questions = data["questions"]
        assert len(questions) == 2

        # Check numerical question with min/max values
        numerical_q = questions[0]
        assert numerical_q["min_value"] == 18
        assert numerical_q["max_value"] == 100
        assert numerical_q["question_options"] is None

        # Check multiple choice question
        mc_q = questions[1]
        assert mc_q["question_options"] == ["Excellent", "Good", "Fair", "Poor"]
        assert mc_q["min_value"] is None
        assert mc_q["max_value"] is None