"""
Remote survey generation client for delegating survey creation to FastAPI server.

This module provides a client for generating surveys remotely when users don't have
local OpenAI API access or explicitly request remote generation. It follows EDSL's
established patterns from the Coop class for HTTP communication and error handling.
"""

from __future__ import annotations
import os
import requests
from typing import Optional, Dict, List, Any
import uuid

from ...logger import get_logger
from ...coop.ep_key_handling import ExpectedParrotKeyHandler
from .exceptions import RemoteSurveyGenerationError, SurveyGenerationError


def should_use_remote(force_remote: bool = False) -> bool:
    """
    Determine whether to use remote survey generation.

    Uses remote generation if:
    1. force_remote=True (explicit user request), OR
    2. OPENAI_API_KEY environment variable is not set or empty

    Args:
        force_remote: Force remote execution even if API key available

    Returns:
        bool: True if should use remote generation, False for local
    """
    if force_remote:
        return True

    # Auto-fallback: use remote if no local API key available
    api_key = os.environ.get("OPENAI_API_KEY")
    return not api_key or api_key.strip() == ""


class RemoteSurveyGenerator:
    """
    Client for remote survey generation via FastAPI server.

    This class handles HTTP communication with the remote survey generation
    service, following EDSL's patterns from the Coop class for consistency
    with existing remote service integrations.

    Configuration:
        EDSL_SURVEY_GENERATION_URL: Base URL for the survey generation service
            Default: http://localhost:8000/api/v1/surveys (local development)

    Authentication:
        Uses EXPECTED_PARROT_API_KEY for server authentication, following
        the same pattern as other EDSL remote services.
    """

    _logger = get_logger(__name__)

    def __init__(self, base_url: Optional[str] = None):
        """
        Initialize the remote survey generator client.

        Args:
            base_url: Base URL for the survey generation service.
                If not provided, uses EDSL_SURVEY_GENERATION_URL from config
                or defaults to local development server.
        """
        self.base_url = (
            base_url
            or os.environ.get("EDSL_SURVEY_GENERATION_URL")
            or "http://localhost:8000/api/v1/surveys"
        )

        if self.base_url.endswith("/"):
            self.base_url = self.base_url[:-1]

        # Initialize key handler for Expected Parrot authentication
        self._key_handler = ExpectedParrotKeyHandler()

    @property
    def headers(self) -> Dict[str, str]:
        """
        Return headers for HTTP requests including authentication.

        Returns:
            dict: HTTP headers with Content-Type, Accept, and Authorization

        Raises:
            RemoteSurveyGenerationError: If Expected Parrot API key is not available
        """
        base_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Add Expected Parrot API key for authentication
        try:
            api_key = self._key_handler.get_key()
            if api_key:
                base_headers["Authorization"] = f"Bearer {api_key}"
            else:
                raise RemoteSurveyGenerationError(
                    "EXPECTED_PARROT_API_KEY is required for remote survey generation. "
                    "Please set this environment variable or use local generation instead."
                )
        except Exception as e:
            raise RemoteSurveyGenerationError(
                f"Failed to get Expected Parrot API key: {str(e)}"
            ) from e

        # Add request ID for tracking
        base_headers["X-Request-ID"] = str(uuid.uuid4())

        return base_headers

    def generate_survey(
        self,
        description: str,
        *,
        num_questions: Optional[int] = None,
        model: str = "gpt-4o",
        temperature: float = 0.7,
        timeout: int = 60,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Generate a survey using the remote service.

        Args:
            description: Natural language description of the survey topic
            num_questions: Optional number of questions to generate
            model: OpenAI model to use (default: "gpt-4o")
            temperature: Temperature for generation (default: 0.7)
            timeout: Request timeout in seconds (default: 60)

        Returns:
            dict: Survey data with "questions" key containing list of question dicts
                Each question dict contains: question_name, question_text, question_type,
                and optional fields like question_options, min_value, max_value

        Raises:
            RemoteSurveyGenerationError: If the remote service fails
            SurveyGenerationError: If survey generation itself fails
            requests.ConnectionError: If cannot connect to server
            requests.Timeout: If request exceeds timeout
        """
        endpoint = f"{self.base_url}/from-vibes"

        # Prepare request payload
        payload = {
            "description": description,
            "model": model,
            "temperature": temperature,
        }

        if num_questions is not None:
            payload["num_questions"] = num_questions

        self._logger.info(f"Sending remote survey generation request to {endpoint}")
        self._logger.debug(f"Request payload: {payload}")

        try:
            # Make the HTTP request
            response = requests.post(
                endpoint,
                json=payload,
                headers=self.headers,
                timeout=timeout,
            )

            # Handle different HTTP status codes
            if response.status_code == 200:
                # Success - parse and validate response
                return self._parse_successful_response(response)

            elif response.status_code == 401:
                # Authentication error
                error_detail = self._extract_error_detail(response)
                error_msg = (
                    f"Authentication failed with remote survey service: {error_detail}. "
                    f"Please check your EXPECTED_PARROT_API_KEY."
                )
                self._logger.error(error_msg)
                raise RemoteSurveyGenerationError(error_msg)

            elif response.status_code == 422:
                # Validation error - likely an issue with the request parameters
                error_detail = self._extract_error_detail(response)
                error_msg = f"Invalid request parameters: {error_detail}"
                self._logger.error(error_msg)
                raise SurveyGenerationError(error_msg)

            elif response.status_code == 500:
                # Server error - likely an issue with survey generation itself
                error_detail = self._extract_error_detail(response)
                error_msg = f"Survey generation failed on server: {error_detail}"
                self._logger.error(error_msg)
                raise SurveyGenerationError(error_msg)

            else:
                # Other HTTP errors
                error_detail = self._extract_error_detail(response)
                error_msg = (
                    f"Remote survey generation failed with status {response.status_code}: "
                    f"{error_detail}"
                )
                self._logger.error(error_msg)
                raise RemoteSurveyGenerationError(error_msg)

        except requests.ConnectionError as e:
            error_msg = (
                f"Could not connect to survey generation service at {endpoint}. "
                f"Please ensure the server is running and accessible."
            )
            self._logger.error(f"{error_msg} Details: {str(e)}")
            raise requests.ConnectionError(error_msg) from e

        except requests.Timeout as e:
            error_msg = (
                f"Request to {endpoint} timed out after {timeout} seconds. "
                f"Try increasing the timeout or check server performance."
            )
            self._logger.error(error_msg)
            raise requests.Timeout(error_msg) from e

        except (RemoteSurveyGenerationError, SurveyGenerationError):
            # Re-raise our custom exceptions
            raise

        except Exception as e:
            error_msg = f"Unexpected error during remote survey generation: {str(e)}"
            self._logger.error(error_msg, exc_info=True)
            raise RemoteSurveyGenerationError(error_msg) from e

    def _parse_successful_response(
        self, response: requests.Response
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Parse and validate a successful response from the server.

        Args:
            response: The HTTP response object

        Returns:
            dict: Validated survey data

        Raises:
            RemoteSurveyGenerationError: If response is invalid
        """
        try:
            result = response.json()
        except ValueError as e:
            error_msg = "Server returned invalid JSON response"
            self._logger.error(f"{error_msg}: {str(e)}")
            raise RemoteSurveyGenerationError(error_msg) from e

        # Validate response structure
        if not isinstance(result, dict):
            error_msg = "Server response is not a valid JSON object"
            self._logger.error(f"{error_msg}: {type(result)}")
            raise RemoteSurveyGenerationError(error_msg)

        if "questions" not in result:
            error_msg = "Invalid response from server: missing 'questions' key"
            self._logger.error(f"{error_msg}. Response keys: {list(result.keys())}")
            raise RemoteSurveyGenerationError(error_msg)

        questions = result["questions"]
        if not isinstance(questions, list):
            error_msg = "Invalid response: 'questions' must be a list"
            self._logger.error(f"{error_msg}: {type(questions)}")
            raise RemoteSurveyGenerationError(error_msg)

        # Basic validation of question structure
        for i, question in enumerate(questions):
            if not isinstance(question, dict):
                error_msg = f"Invalid question at index {i}: must be an object"
                self._logger.error(error_msg)
                raise RemoteSurveyGenerationError(error_msg)

            required_fields = ["question_name", "question_text", "question_type"]
            for field in required_fields:
                if field not in question:
                    error_msg = (
                        f"Invalid question at index {i}: missing '{field}' field"
                    )
                    self._logger.error(error_msg)
                    raise RemoteSurveyGenerationError(error_msg)

        self._logger.info(f"Successfully generated {len(questions)} questions remotely")
        self._logger.debug(
            f"Question types: {[q.get('question_type') for q in questions]}"
        )

        return result

    def _extract_error_detail(self, response: requests.Response) -> str:
        """
        Extract error detail from response, handling various formats.

        Args:
            response: The HTTP response object

        Returns:
            str: Error detail message
        """
        try:
            error_data = response.json()
            # FastAPI typically uses "detail" key for error messages
            if isinstance(error_data, dict) and "detail" in error_data:
                return str(error_data["detail"])
            elif isinstance(error_data, dict) and "message" in error_data:
                return str(error_data["message"])
            else:
                return str(error_data)
        except (ValueError, TypeError):
            # Fall back to raw response text
            return response.text or f"HTTP {response.status_code}"

    def health_check(self, timeout: int = 10) -> bool:
        """
        Check if the remote survey generation service is available.

        Args:
            timeout: Request timeout in seconds (default: 10)

        Returns:
            bool: True if service is available, False otherwise
        """
        try:
            # Try to reach a health endpoint or the root endpoint
            health_url = self.base_url.replace("/api/v1/surveys", "/health")
            if health_url == self.base_url:
                # If URL didn't change, try root
                health_url = self.base_url.rsplit("/", 1)[0] + "/health"

            response = requests.get(
                health_url, timeout=timeout, headers={"Accept": "application/json"}
            )

            return response.status_code in (200, 404)  # 404 is OK, means server is up

        except Exception as e:
            self._logger.debug(f"Health check failed: {str(e)}")
            return False
