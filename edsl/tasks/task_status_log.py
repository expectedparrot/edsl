"""
This module provides the TaskStatusLog class for tracking the status history of tasks.

The TaskStatusLog class maintains an ordered list of status changes for a specific task,
with timestamps and status values. This history allows for detailed analysis of task
execution, including timing, state transitions, and status at any point in time.
"""

from collections import UserList

from .task_status_enum import TaskStatus


class TaskStatusLog(UserList):
    """
    An ordered history of status changes for a single task.
    
    This class extends UserList to provide a chronological record of all status changes
    that a task undergoes during its lifecycle. Each entry in the list is a 
    TaskStatusLogEntry object containing a timestamp and status value.
    
    The TaskStatusLog provides methods to analyze the timing of task execution and 
    determine task status at any point in time. This information is valuable for
    debugging, performance analysis, and visualization of task execution flow.
    
    Key features:
    - Records all status transitions with timestamps
    - Provides min/max execution time calculations
    - Supports interpolation to determine status at any given time
    - Used by visualization tools to render task execution timelines
    """

    @property
    def min_time(self) -> float:
        """
        Get the timestamp of the first status change.
        
        Returns:
            The timestamp (from time.monotonic()) of the earliest status entry
            
        Note:
            This is typically when the task was first created and set to NOT_STARTED
        """
        return self[0]["log_time"]

    @property
    def max_time(self) -> float:
        """
        Get the timestamp of the last status change.
        
        Returns:
            The timestamp (from time.monotonic()) of the most recent status entry
            
        Note:
            This is typically when the task reached its final state (SUCCESS, FAILED, etc.)
        """
        return self[-1]["log_time"]

    def status_at_time(self, t: float) -> TaskStatus:
        """
        Determine what status the task had at a specific point in time.
        
        This method interpolates between status log entries to determine the task's
        status at any arbitrary time point. It searches for the first status change
        that occurred after time t and returns the status that was active at that time.
        
        Parameters:
            t: The timestamp to query (from time.monotonic())
            
        Returns:
            The TaskStatus that was active at time t
            
        Note:
            If t is after the last recorded status change, the final status is returned.
            If t is before the first recorded status change, this method may not behave
            as expected since it assumes ordered traversal through the log.
            
        TODO: 
            Could re-factor with bisect to make this faster for large logs.
        """
        for entry in self:
            if entry["log_time"] > t:
                return entry["value"]
        return self[-1]["value"]
