from collections import UserDict

from ..tasks.task_status_enum import TaskStatus, status_colors


class InterviewStatusLog(UserDict):
    """A dictionary of TaskStatusLog objects.

    The key is the name of the task.
    """

    @property
    def min_time(self) -> float:
        """Return the minimum time of the status log."""
        return min([log.min_time for log in self.values()])

    @property
    def max_time(self) -> float:
        """Return the maximum time of the status log."""
        return max([log.max_time for log in self.values()])

    def status_matrix(self, num_periods: int) -> dict[str, list[TaskStatus]]:
        """Return a matrix of status values."""
        start_time = self.min_time
        end_time = self.max_time
        time_increment = (end_time - start_time) / num_periods
        status_matrix = {}
        time_periods = [start_time + i * time_increment for i in range(num_periods)]
        for task_name, log in self.items():
            status_matrix[task_name] = [log.status_at_time(t) for t in time_periods]
        return status_matrix

    def numerical_matrix(
        self, num_periods: int
    ) -> tuple[list[list[int]], dict[int, str]]:
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


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
