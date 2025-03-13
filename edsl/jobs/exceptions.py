from textwrap import dedent

from ..base import BaseException

class JobsErrors(BaseException):
    """
    Base exception class for all job-related errors.
    
    This is the parent class for all exceptions related to job execution
    in the EDSL framework. It provides a common type for catching any
    job-specific error.
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/jobs.html"


class JobsRunError(JobsErrors):
    """
    Exception raised when a job fails to run correctly.
    
    This exception indicates issues with job execution such as:
    - Configuration problems before job execution
    - Resource allocation failures
    - Job termination due to internal errors
    
    To fix this error:
    1. Check the job configuration for any invalid parameters
    2. Ensure all required resources (models, agents, etc.) are available
    3. Verify that dependent services are accessible
    
    Note: This exception is currently not used actively in the codebase,
    but is kept for potential future use and test cases.
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/jobs.html"


class MissingRemoteInferenceError(JobsErrors):
    """
    Exception raised when remote inference is required but not configured.
    
    This exception occurs when:
    - A job requires remote inference capabilities but they're not available
    - Credentials for remote inference are missing or invalid
    
    To fix this error:
    1. Set up remote inference configuration in your environment
    2. Provide valid API keys for the required inference service
    
    Note: This exception is defined but not currently used in the codebase.
    It raises Exception("not used") to indicate this state.
    """
    def __init__(self, message="Remote inference configuration is missing", **kwargs):
        super().__init__(message, **kwargs)
        raise Exception("not used")


class InterviewError(Exception):
    """
    Base exception class for all interview-related errors.
    
    This exception serves as the parent class for specific interview errors
    and handles cases where an interview process fails for reasons not covered
    by more specific exceptions.
    """
    
    def __init__(self, message="An error occurred during the interview process"):
        super().__init__(message)
        self.message = message


class InterviewErrorPriorTaskCanceled(InterviewError):
    """
    Exception raised when a task cannot run because a dependent task failed.
    
    This exception is raised in task pipelines when a prerequisite task
    fails or is canceled, preventing dependent tasks from executing.
    
    When you encounter this error:
    1. Check the error logs for information about the failed dependent task
    2. Fix any issues with the prerequisite task first before retrying
    3. If using custom task dependencies, verify that the dependency chain is correct
    """
    
    def __init__(self, message="Cannot run this task because a required prior task was canceled or failed"):
        super().__init__(message)


class InterviewTimeoutError(InterviewError):
    """
    Exception raised when an interview operation times out.
    
    This exception indicates that a model call or other operation
    during an interview process took too long to complete.
    
    To fix this error:
    1. Check your network connection if using remote models
    2. Consider increasing timeout settings if dealing with complex prompts
    3. Try a different model provider if consistently experiencing timeouts
    
    Note: While defined here, the codebase currently uses LanguageModelNoResponseError
    to handle timeouts in actual operation.
    """
    
    def __init__(self, message="The interview operation timed out"):
        super().__init__(message)
