from __future__ import annotations
from collections import UserDict
import enum
import time


class TaskStatus(enum.Enum):
    """
    Enumeration of possible states for a task in the EDSL task system.
    
    Each task moves through various states during its lifecycle, from creation 
    to completion. This enum defines all possible states to track task progress 
    and diagnose issues.
    
    States:
        NOT_STARTED: Initial state - task has been created but not yet started
        WAITING_FOR_DEPENDENCIES: Task is waiting for prerequisite tasks to complete
        CANCELLED: Task was explicitly cancelled by the user or system
        PARENT_FAILED: Task cannot run because a dependency task failed
        WAITING_FOR_REQUEST_CAPACITY: Task is waiting due to API rate limits
        WAITING_FOR_TOKEN_CAPACITY: Task is waiting due to token usage limits
        API_CALL_IN_PROGRESS: Task is actively executing an API call
        SUCCESS: Task completed successfully
        FAILED: Task encountered an error and failed to complete
    
    These states are used throughout EDSL to track task progress, generate
    visualizations, and provide detailed error reports.
    """
    NOT_STARTED = enum.auto()
    WAITING_FOR_DEPENDENCIES = enum.auto()
    CANCELLED = enum.auto()
    PARENT_FAILED = enum.auto()
    WAITING_FOR_REQUEST_CAPACITY = enum.auto()
    WAITING_FOR_TOKEN_CAPACITY = enum.auto()
    API_CALL_IN_PROGRESS = enum.auto()
    SUCCESS = enum.auto()
    FAILED = enum.auto()


class TaskStatusLogEntry(UserDict):
    """
    A timestamped record of a task's status change.
    
    This class records both the time when a task's status changed and the new status value.
    It uses the UserDict interface for convenient dictionary-like access while maintaining
    the structured nature of status log entries.
    
    Attributes:
        log_time: The time (from time.monotonic()) when the status change occurred
        value: The new TaskStatus value
    """
    def __init__(self, log_time: float, value: TaskStatus):
        """
        Create a new task status log entry.
        
        Parameters:
            log_time: The time when this status change occurred (from time.monotonic())
            value: The TaskStatus value that the task transitioned to
        """
        self.data = {"log_time": log_time, "value": value}
        super().__init__(self.data)


class TaskStatusDescriptor:
    """
    A descriptor that enforces TaskStatus type safety and logs status changes.
    
    This descriptor is used to create task_status properties in task-related classes.
    It performs two key functions:
    
    1. Type Enforcement: Ensures that task_status is always set to a valid TaskStatus enum
    2. Logging: Automatically adds entries to the task's status_log when status changes
    
    By using this descriptor, EDSL ensures consistent status tracking across all tasks
    while providing a rich history of status changes for debugging and visualization.
    """

    def __init__(self):
        """Initialize the descriptor with a null status value."""
        self._task_status = None

    def __get__(self, instance, owner):
        """Return the current task status."""
        return self._task_status

    def __set__(self, instance, value):
        """
        Set a new task status and record the change in the status log.
        
        This method enforces that the value is a valid TaskStatus enum and
        automatically adds an entry to the instance's status_log (if it exists).
        
        Parameters:
            instance: The object instance that owns this descriptor
            value: The new TaskStatus value to set
            
        Raises:
            ValueError: If value is not an instance of TaskStatus enum
        """
        if not isinstance(value, TaskStatus):
            raise ValueError("Value must be an instance of TaskStatus enum")
        
        # Record the current time for the status change
        t = time.monotonic()
        
        # Add an entry to the status log if the instance has one
        if hasattr(instance, "status_log"):
            instance.status_log.append(TaskStatusLogEntry(t, value))
            
        # Update the actual status value
        self._task_status = value

    def __delete__(self, instance):
        """Reset the task status to None when deleted."""
        self._task_status = None


status_colors = {
    TaskStatus.NOT_STARTED: "grey",
    TaskStatus.WAITING_FOR_DEPENDENCIES: "orange",
    TaskStatus.WAITING_FOR_REQUEST_CAPACITY: "yellow",
    TaskStatus.WAITING_FOR_TOKEN_CAPACITY: "gold",
    TaskStatus.CANCELLED: "white",
    TaskStatus.PARENT_FAILED: "darkred",
    TaskStatus.FAILED: "red",
    TaskStatus.API_CALL_IN_PROGRESS: "blue",
    TaskStatus.SUCCESS: "green",
}


def get_enum_from_string(str_key):
    """Parse the string to extract the enum member name."""
    try:
        _, member_name = str_key.split(".")
        enum_member = getattr(TaskStatus, member_name)
        return enum_member
    except ValueError:
        return str_key


class InterviewTaskLogDict(UserDict):
    """
    A collection of task status logs for all tasks in an interview.
    
    This dictionary-like object maps task names to their individual TaskStatusLog objects,
    providing methods to analyze task execution across an entire interview. It supports
    calculating timing metrics, generating status matrices for visualization, and 
    rendering graphical representations of task execution flow.
    
    The InterviewTaskLogDict is a key component in EDSL's task monitoring system,
    enabling both debugging of individual interviews and aggregate analysis of
    execution patterns.
    
    Key features:
    - Temporal analysis (min/max execution times)
    - Status matrix generation for visualization
    - Visual representation of task status changes over time
    - Color-coded status visualization
    """

    @property
    def min_time(self):
        return min([log.min_time for log in self.values()])

    @property
    def max_time(self):
        return max([log.max_time for log in self.values()])

    def status_matrix(self, num_periods):
        """Return a matrix of status values."""
        start_time = self.min_time
        end_time = self.max_time
        time_increment = (end_time - start_time) / num_periods
        status_matrix = {}
        time_periods = [start_time + i * time_increment for i in range(num_periods)]
        for task_name, log in self.items():
            status_matrix[task_name] = [log.status_at_time(t) for t in time_periods]
        return status_matrix

    def numerical_matrix(self, num_periods):
        """Return a numerical matrix of status values."""
        status_dicts = self.status_matrix(num_periods)

        num_cols = num_periods
        num_rows = len(status_dicts)
        matrix = [[0 for _ in range(num_cols)] for _ in range(num_rows)]

        for row_index, (task_name, status_list) in enumerate(status_dicts.items()):
            matrix[row_index] = [
                list(status_colors.keys()).index(status) for status in status_list
            ]

        index_to_names = {i: name for i, name in enumerate(status_dicts.keys())}
        return matrix, index_to_names

    def visualize(self, num_periods=10):
        """Visualize the status matrix with outlined squares."""
        import matplotlib.pyplot as plt
        from matplotlib.colors import ListedColormap
        import numpy as np
        from matplotlib.patches import Rectangle

        # Define your custom colormap
        custom_cmap = ListedColormap(list(status_colors.values()))

        # Generate the matrix
        matrix, index_to_names = self.numerical_matrix(num_periods)

        # Create the figure and axes
        plt.figure(figsize=(10, 5))
        ax = plt.gca()

        # Display the matrix and keep a reference to the imshow object
        im = ax.imshow(matrix, aspect="auto", cmap=custom_cmap)

        # Adding color bar, now correctly associating it with 'im'
        cbar = plt.colorbar(im, ticks=range(len(status_colors)), label="Task Status")

        cbar_labels = [status.name for status in status_colors.keys()]
        # breakpoint()
        cbar.set_ticklabels(cbar_labels)  # Setting the custom labels for the colorbar

        im.set_clim(
            -0.5, len(status_colors) - 0.5
        )  # Setting color limits directly on the imshow object

        # Outline each cell by drawing rectangles
        for (j, i), val in np.ndenumerate(matrix):
            ax.add_patch(
                Rectangle(
                    (i - 0.5, j - 0.5), 1, 1, fill=False, edgecolor="black", lw=0.5
                )
            )

        # Set custom y-axis ticks and labels
        yticks = list(index_to_names.keys())
        yticklabels = list(index_to_names.values())
        plt.yticks(ticks=yticks, labels=yticklabels)

        # Show the plot
        plt.show()


if __name__ == "__main__":
    pass
