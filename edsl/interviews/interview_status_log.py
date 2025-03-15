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

    def visualize(self, num_periods: int = 10) -> None:
        """Visualize the status matrix with outlined squares."""
        import matplotlib.pyplot as plt
        import numpy as np
        from matplotlib.colors import ListedColormap
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
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
