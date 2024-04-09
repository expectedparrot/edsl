"""A module for status logs and status objects.

A StatusObject is a dictionary. 

For example, for a given task, it could be:
{
    'status': TaskStatus.SUCCESS,
    'tokens_used': 100,
}

Then, an aggregate like an InterviewStatusObject is some aggregation of these status objects.

These are then stored in a log as entries with a time stamp.
The aggregation, again at the level of a specific task, could be 
{
    'final_status': TaskStatus.SUCCESS,
    'elapsed_time': 100,
}

For an interview, it could be: 
{
    'status': InterviewStatus.WAITING_FOR_RESOURCES,
    'tokens_used': 10_00,
}
"""
from abc import ABC, abstractmethod
import time

from collections import UserList, UserDict


class StatusObjectABC(ABC, UserDict):
    """An abstract base class for status objects.

    This is a snapshot of this object at a moment in time.
    -For example, for a task, it could be just the state of the task.
    -For an interivew, could be the states of the all the component tasks.
    -For a job, it could be the states of all the interviews.

    An abstract base class for status objects.
    """

    @abstractmethod
    def state(self):
        """Return the state of the status object, which must be from a specified enum."""
        pass

    @abstractmethod
    def __repr__(self) -> str:
        """Return a string representation of the status object."""
        pass

    @abstractmethod
    def to_dict(self) -> dict:
        """Return the status object as a dictionary."""
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data_dict) -> "StatusObjectABC":
        """Return a status object from a dictionary."""
        pass


class CumulativeStatusObjectABC(ABC):
    """An abstract base class for cumulative status objects."""

    def __init__(self, value):
        """Initialize the object with a value."""
        self.value = value

    def add(self, new_object):
        """Add a new object to the cumulative object."""
        pass


class StatusLogABC(ABC, UserList):
    """For example, these could be status of a task, or the status of a job."""

    def __init__(self, data=None):
        """Initialize the log with the given data."""
        if data is None:
            data = []
        super().__init__(data)
        self._cumulative_state = None

    @classmethod
    def __init_subclass__(cls, **kwargs):
        """Check that the subclass has a status_enum attribute."""
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, "status_enum"):
            raise TypeError(f"{cls.__name__} is missing 'status_enum' class attribute")

    @property
    def current(self):
        """Return the most recently added status."""
        self._check()
        return self[-1]

    def _check(self):
        """Check that the log is not empty."""
        if len(self) == 0:
            raise Exception("No data in log")

    # def reduce(self):
    #     """Reduce a list of status objects to a single status object."""
    #     _, result = self[0]
    #     for _, status in self[1:]:
    #         result += status
    #     return result

    def log(self, status) -> None:
        """Check to make sure time is later."""
        t = time.monotonic()
        if len(self) > 0 and self[-1][0] > t:
            raise ValueError("Time must be later than previous time")

        self.append((t, status))

    def status_at_time(self, target_time):
        """Return the status at a given time."""
        for t, status in reversed(self.data):
            if t <= target_time:
                return status
        return None

    @abstractmethod
    def __repr__(self):
        """Return a string representation of the log."""
        pass

    @property
    def min_time(self):
        """Return the earliest time in the log."""
        if len(self) == 0:
            raise Exception("No data in log")
        return self[0][0]

    @property
    def max_time(self):
        """Return the latest time in the log."""
        if len(self) == 0:
            raise Exception("No data in log")
        return self[-1][0]

    def to_dict(self):
        """Return the log as a dictionary."""
        return {"data": [(t, status.to_dict()) for t, status in self.data]}

    @classmethod
    def from_dict(cls, data_dict):
        """Return a log from a dictionary."""
        obj = cls()
        data = data_dict["data"]
        for t, status in data:
            obj.append(t, status.from_dict())

    def status_vector(self, num_periods=10):
        """Return a matrix of status values."""
        start_time = self.min_time
        end_time = self.max_time
        time_increment = (end_time - start_time) / num_periods
        time_periods = [start_time + i * time_increment for i in range(num_periods)]
        status_vector = [self.status_at_time(t) for t in time_periods]
        return status_vector

    def state_vector(self, num_periods=10):
        """Return a vector of status values."""
        status_vector = self.status_vector(num_periods)
        return [status.state() for status in status_vector]

    def state_vector_with_colors(self, num_periods):
        """Return a vector of status values."""
        status_vector = self.status_vector(num_periods)
        return [self.status_color_dict[status] for status in status_vector]

    # def numerical_matrix(self, num_periods):
    #     """Return a numerical matrix of status values."""
    #     status_dicts = self.status_vector(num_periods)

    #     num_cols = num_periods
    #     num_rows = len(status_dicts)
    #     matrix = [[0 for _ in range(num_cols)] for _ in range(num_rows)]

    #     for row_index, (task_name, status_list) in enumerate(status_dicts.items()):
    #         matrix[row_index] = [list(status_colors.keys()).index(status) for status in status_list]

    #     index_to_names = {i: name for i, name in enumerate(status_dicts.keys())}
    #     return matrix, index_to_names

    # def visualize(self, num_periods=10):
    #     """Visualize the status matrix with outlined squares."""
    #     import matplotlib.pyplot as plt
    #     from matplotlib.colors import ListedColormap
    #     import numpy as np
    #     from matplotlib.patches import Rectangle

    #     # Define your custom colormap
    #     custom_cmap = ListedColormap(list(status_colors.values()))

    #     # Generate the matrix
    #     matrix, index_to_names = self.numerical_matrix(num_periods)

    #     # Create the figure and axes
    #     plt.figure(figsize=(10, 5))
    #     ax = plt.gca()

    #     # Display the matrix and keep a reference to the imshow object
    #     im = ax.imshow(matrix, aspect='auto', cmap=custom_cmap)

    #     # Adding color bar, now correctly associating it with 'im'
    #     cbar = plt.colorbar(im, ticks=range(len(status_colors)), label='Task Status')

    #     cbar_labels = [status.name for status in status_colors.keys()]
    #     #breakpoint()
    #     cbar.set_ticklabels(cbar_labels)  # Setting the custom labels for the colorbar

    #     im.set_clim(-0.5, len(status_colors) - 0.5)  # Setting color limits directly on the imshow object

    #     # Outline each cell by drawing rectangles
    #     for (j, i), val in np.ndenumerate(matrix):
    #         ax.add_patch(Rectangle((i - 0.5, j - 0.5), 1, 1, fill=False, edgecolor='black', lw=0.5))

    #     # Set custom y-axis ticks and labels
    #     yticks = list(index_to_names.keys())
    #     yticklabels = list(index_to_names.values())
    #     plt.yticks(ticks=yticks, labels=yticklabels)

    #     # Show the plot
    #     plt.show()


if __name__ == "__main__":
    import doctest

    doctest.testmod()

    import enum

    class ExampleStatusEnum(enum.Enum):
        """An example of a status enum."""

        NOT_STARTED = enum.auto()
        IN_PROGRESS = enum.auto()
        SUCCESS = enum.auto()
        FAILED = enum.auto()

    class ExampleStatus(StatusObjectABC):
        """An example of a status object."""

        status_enum = ExampleStatusEnum
        status_color_dict = {
            ExampleStatusEnum.NOT_STARTED: "grey",
            ExampleStatusEnum.IN_PROGRESS: "orange",
            ExampleStatusEnum.SUCCESS: "green",
            ExampleStatusEnum.FAILED: "red",
        }

        def __init__(self, value):
            """Initialize the status object with a value."""
            self.value = value

        def state(self):
            """Return the state of the status object."""
            return self.value

        def __repr__(self):
            """Return a string representation of the status object."""
            return f"ExampleStatus(value = {self.value})"

        def to_dict(self):
            """Return the status object as a dictionary."""
            return {"example_key": "example_value"}

        @classmethod
        def from_dict(cls, data_dict):
            """Return a status object from a dictionary."""
            return cls()

    class ExampleStatusLog(StatusLogABC):
        """An example of a status log."""

        status_enum = ExampleStatusEnum

        def __repr__(self):
            """Return a string representation of the log."""
            return f"ExampleStatusLog(data = {[(t, repr(status)) for t, status in self.data]})"

    example_status1 = ExampleStatus(ExampleStatusEnum.NOT_STARTED)
    example_status2 = ExampleStatus(ExampleStatusEnum.IN_PROGRESS)
    example_status3 = ExampleStatus(ExampleStatusEnum.SUCCESS)

    log = ExampleStatusLog()
    log.log(example_status1)
    log.log(example_status2)
    log.log(example_status3)

    print(log.to_dict())

    log.current
    log.min_time
    log.max_time
    log.status_vector()
