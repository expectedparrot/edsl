"""
This module defines the exception hierarchy for the tasks module.

All exceptions related to task creation, execution, and management are defined here.
These exceptions provide detailed error information for debugging and error reporting.
"""

from ..base import BaseException


class TaskError(BaseException):
    """
    Base exception for all tasks-related errors.
    
    This is the parent class for all exceptions raised within the tasks module.
    It inherits from BaseException to ensure proper error tracking and reporting.
    """
    pass


class TaskStatusError(TaskError):
    """
    Raised when a task encounters an invalid status transition.
    
    This exception is raised when a task attempts to transition to an invalid state
    based on its current state, such as trying to set a completed task to running.
    
    Attributes:
        current_status: The current status of the task
        attempted_status: The status that could not be set
    """
    pass


class TaskExecutionError(TaskError):
    """
    Raised when a task encounters an error during execution.
    
    This is a general exception for errors that occur while a task is running,
    not specific to dependency resolution or resource allocation.
    """
    pass


class TaskDependencyError(TaskError):
    """
    Raised when there is an issue with task dependencies.
    
    This exception is raised for dependency-related issues, such as circular
    dependencies or errors in dependent tasks.
    """
    pass


class TaskResourceError(TaskError):
    """
    Raised when a task cannot acquire necessary resources.
    
    This exception is used when a task cannot obtain required resources
    such as tokens or request capacity, beyond normal waiting situations.
    """
    pass


class TaskHistoryError(TaskError):
    """
    Raised for errors related to task history operations.
    
    This exception covers issues with recording, accessing, or analyzing
    task execution history and logs.
    """
    pass