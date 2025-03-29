"""
The tasks module provides EDSL's task management system for tracking and controlling 
interview execution.

This module implements a comprehensive system for creating, scheduling, executing, and 
monitoring tasks in EDSL. Tasks represent individual units of work, typically answering 
a question with an LLM, with features for dependency management, error handling, and 
execution status tracking.

Key components:

1. TaskHistory - Records and analyzes the execution history of tasks with error reporting
2. QuestionTaskCreator - Creates and manages tasks for individual questions
3. TaskCreators - Manages collections of tasks for an entire interview
4. TaskStatus - Enumeration of possible task states (running, waiting, success, etc.)
5. TaskStatusLog - Records the status changes of tasks over time

The tasks system helps EDSL manage complex interview workflows by:
- Handling dependencies between questions
- Managing API rate limits and token usage
- Providing detailed execution metrics
- Generating error reports and visualizations
- Supporting both synchronous and asynchronous execution

For most users, this module works behind the scenes, but understanding it can 
be helpful when debugging or optimizing complex EDSL workflows.
"""

__all__ = [
    'TaskHistory', 
    'QuestionTaskCreator', 
    'TaskCreators', 
    'TaskStatus', 
    'TaskStatusDescriptor',
    'TaskError',
    'TaskStatusError',
    'TaskExecutionError',
    'TaskDependencyError',
    'TaskResourceError',
    'TaskHistoryError'
]

from .task_history import TaskHistory
from .question_task_creator import QuestionTaskCreator
from .task_creators import TaskCreators
from .task_status_enum import TaskStatus, TaskStatusDescriptor
from .exceptions import (
    TaskError,
    TaskStatusError,
    TaskExecutionError,
    TaskDependencyError,
    TaskResourceError,
    TaskHistoryError
)