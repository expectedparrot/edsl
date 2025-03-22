"""
This module provides the TaskCreators class, which manages all task creators for an interview.

The TaskCreators class maintains a dictionary of QuestionTaskCreator objects, each responsible
for executing a single question within an interview. It aggregates status and token usage
information across all tasks, providing a complete view of interview execution.
"""

from typing import List, TYPE_CHECKING
from collections import UserDict

if TYPE_CHECKING:
    from ..tokens import InterviewTokenUsage
    from ..interviews import InterviewStatusDictionary
    from .task_status_log import TaskStatusLog

class TaskCreators(UserDict):
    """
    A collection manager for all question tasks within an interview.
    
    The TaskCreators class maintains a dictionary of QuestionTaskCreator objects,
    where each key is a question name and each value is the corresponding task creator.
    This class provides methods to aggregate information across all tasks, such as
    token usage and status counts, enabling a holistic view of interview execution.
    
    In the EDSL architecture, an interview consists of multiple questions, each executed
    as a separate task. The TaskCreators class helps track and manage these tasks,
    maintaining their execution status and resource usage.
    
    Key features:
    - Maintains a mapping of question names to their task creators
    - Aggregates token usage across all tasks
    - Tracks the status of all tasks in the interview
    - Provides access to status logs for visualization and analysis
    
    This class is typically used by the Interview class to manage task execution
    and track the overall status of the interview.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def token_usage(self) -> 'InterviewTokenUsage':
        """
        Calculate the total token usage across all tasks in the interview.
        
        This property aggregates token usage statistics from all task creators,
        separating cached tokens (reused from cache) from new tokens (freshly generated).
        The resulting InterviewTokenUsage object provides a complete picture of token
        consumption for the entire interview.
        
        Returns:
            An InterviewTokenUsage object containing:
            - Cached token usage (tokens reused from cache)
            - New token usage (tokens freshly generated)
            
        Notes:
            - This is useful for cost estimation and quota management
            - The separation of cached vs. new tokens helps analyze caching effectiveness
            - Token usage is tracked separately for prompts and completions
        """
        from ..tokens import TokenUsage
        from ..tokens import InterviewTokenUsage

        cached_tokens = TokenUsage(from_cache=True)
        new_tokens = TokenUsage(from_cache=False)
        for task_creator in self.values():
            token_usage = task_creator.token_usage()
            cached_tokens += token_usage["cached_tokens"]
            new_tokens += token_usage["new_tokens"]
        return InterviewTokenUsage(
            new_token_usage=new_tokens, cached_token_usage=cached_tokens
        )

    @property
    def interview_status(self) -> 'InterviewStatusDictionary':
        """
        Get a summary of task statuses across the entire interview.
        
        This property counts how many tasks are in each possible status state,
        providing a snapshot of the interview's current execution state. The
        resulting InterviewStatusDictionary maps each TaskStatus to a count
        of tasks in that state, plus a special 'number_from_cache' counter.
        
        Returns:
            An InterviewStatusDictionary with counts for each task status
            
        Notes:
            - Used for monitoring interview progress
            - Helps identify bottlenecks (many tasks waiting for capacity)
            - Tracks cache utilization via the 'number_from_cache' count
            - Useful for status dashboards and progress reporting
            
        Example:
            >>> t = TaskCreators()
            >>> status = t.interview_status
            >>> 'number_from_cache' in status
            True
            >>> status['number_from_cache']  # Check the cache count
            0
        """
        from ..interviews import InterviewStatusDictionary
        status_dict = InterviewStatusDictionary()
        for task_creator in self.values():
            status_dict[task_creator.task_status] += 1
            status_dict["number_from_cache"] += task_creator.from_cache
        return status_dict

    def status_logs(self) -> List['TaskStatusLog']:
        """
        Get all task status logs for the interview.
        
        This method collects the status logs from all task creators, providing
        a complete history of status changes for every task in the interview.
        The resulting list can be used for detailed analysis of task execution
        patterns, timing, and visualization.
        
        Returns:
            A list of TaskStatusLog objects, one for each task in the interview
            
        Notes:
            - Used by visualization tools like task timeline charts
            - Helpful for performance analysis and bottleneck identification
            - Provides data for execution reports and dashboards
        """
        return [task_creator.status_log for task_creator in self.values()]


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
