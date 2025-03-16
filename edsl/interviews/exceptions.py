"""
Exceptions specific to the interviews module.

This module defines custom exception classes for all interview-related errors
in the EDSL framework, ensuring consistent error handling and user feedback.
"""

from ..base import BaseException


class InterviewError(BaseException):
    """
    Base exception class for all interview-related errors.
    
    This is the parent class for all exceptions related to interview creation,
    execution, and management in the EDSL framework.
    
    Examples:
        ```python
        # Usually not raised directly, but through subclasses
        # For example, when accessing incomplete tasks
        interview.get_completed_task("incomplete_task")  # Would raise InterviewTaskError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/interviews.html"


class InterviewTaskError(InterviewError):
    """
    Exception raised when there's an issue with interview tasks.
    
    This exception occurs when:
    - Attempting to access tasks that are not complete
    - Task execution fails due to errors in the model response
    - Task dependencies are not satisfied
    
    Examples:
        ```python
        # Attempting to access an incomplete task
        interview.get_completed_task("incomplete_task")  # Raises InterviewTaskError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/interviews.html"


class InterviewStatusError(InterviewError):
    """
    Exception raised when there's an issue with interview status management.
    
    This exception occurs when:
    - Invalid operations are performed on interview status objects
    - Incompatible status objects are combined
    - Status tracking encounters inconsistent states
    
    Examples:
        ```python
        # Attempting to add incompatible status objects
        status_dict + incompatible_object  # Raises InterviewStatusError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/interviews.html"


class InterviewTokenError(InterviewError):
    """
    Exception raised when there's an issue with token estimation or usage.
    
    This exception occurs when:
    - Invalid inputs are provided to token estimators
    - Token calculation fails due to unsupported prompt types
    - Token limits are exceeded during an interview
    
    Examples:
        ```python
        # Providing an invalid prompt type to token estimator
        estimator.estimate_tokens(invalid_prompt)  # Raises InterviewTokenError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/token_usage.html"