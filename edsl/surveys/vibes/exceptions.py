"""
Exceptions specific to the vibes survey generation module.

This module defines exception classes for various error conditions that can
occur when using vibes functionality, including remote survey generation
and local survey creation from natural language descriptions.
"""

from ...base import BaseException


class VibesError(BaseException):
    """
    Base class for all vibes-related exceptions.

    This is the parent class for all exceptions raised by the vibes module.
    It inherits from EDSL's BaseException to maintain consistency with
    the library's exception hierarchy.

    When catching errors from vibes operations, you can catch this exception
    to handle all vibes-related errors in a single exception handler.
    """

    relevant_doc = "https://docs.expectedparrot.com/en/latest/surveys.html#vibes"


class RemoteSurveyGenerationError(VibesError):
    """
    Exception raised when remote survey generation fails.

    This exception is raised when the remote survey generation service
    returns an error or cannot be reached. This typically occurs when:
    - The remote server is unavailable or unreachable
    - Authentication fails (missing or invalid Expected Parrot API key)
    - The server returns an error response (OpenAI API issues, etc.)
    - Network connectivity problems prevent communication

    To fix this error:
    1. Check your network connection and ensure you can reach the server
    2. Verify that EXPECTED_PARROT_API_KEY is set and valid
    3. Try using local generation by setting OPENAI_API_KEY instead
    4. Check if the remote service is available and running
    5. Look at the specific error message for more detailed guidance

    Example:
        ```python
        # This might raise RemoteSurveyGenerationError if server is down
        survey = Survey.from_vibes("Customer satisfaction survey", remote=True)
        ```

    Alternative solutions:
        ```python
        # Use local generation instead
        import os
        os.environ["OPENAI_API_KEY"] = "your-openai-key"
        survey = Survey.from_vibes("Customer satisfaction survey")  # Uses local
        ```
    """

    relevant_doc = (
        "https://docs.expectedparrot.com/en/latest/surveys.html#remote-generation"
    )


class SurveyGenerationError(VibesError):
    """
    Exception raised when survey generation fails due to content or model issues.

    This exception is raised when the survey generation process fails, typically
    due to issues with the language model, malformed responses, or content
    validation problems. This can occur in both local and remote generation.

    Common causes:
    - OpenAI API errors or rate limits
    - Invalid or insufficient description provided
    - Model response parsing failures
    - Content policy violations

    To fix this error:
    1. Check the specific error message for details
    2. Try rephrasing your survey description to be more specific
    3. Ensure your OpenAI API key has sufficient quota/credits
    4. Try using a different model parameter (e.g., "gpt-4o" instead of "gpt-4")
    5. Reduce the temperature parameter for more consistent results

    Example:
        ```python
        # This might raise SurveyGenerationError with unclear description
        survey = Survey.from_vibes("stuff")  # Too vague

        # Better approach
        survey = Survey.from_vibes(
            "Employee satisfaction survey for a tech company with questions about "
            "work-life balance, compensation, and career development"
        )
        ```
    """

    relevant_doc = (
        "https://docs.expectedparrot.com/en/latest/surveys.html#troubleshooting"
    )
