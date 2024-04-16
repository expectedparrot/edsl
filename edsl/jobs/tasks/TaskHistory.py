from edsl.jobs.tasks.task_status_enum import TaskStatus
from matplotlib import pyplot as plt
from typing import List


class TaskHistory:
    def __init__(self, interviews: List["Interview"], include_traceback=False):
        self.total_interviews = interviews
        self.include_traceback = include_traceback

        self.exceptions = [
            i.exceptions
            for index, i in enumerate(self.total_interviews)
            if i.exceptions != {}
        ]
        self.indices = [
            index for index, i in enumerate(self.total_interviews) if i.exceptions != {}
        ]

    def to_dict(self):
        """Return the TaskHistory as a dictionary."""
        return {
            "exceptions": [
                e.to_dict(include_traceback=self.include_traceback)
                for e in self.exceptions
            ],
            "indices": self.indices,
        }

    @property
    def has_exceptions(self) -> bool:
        """Return True if there are any exceptions."""
        return len(self.exceptions) > 0

    def _repr_html_(self):
        """Return an HTML representation of the TaskHistory."""
        from edsl.utilities.utilities import data_to_html

        newdata = self.to_dict()["exceptions"]
        return data_to_html(newdata, replace_new_lines=True)

    def show_exceptions(self):
        """Print the exceptions."""
        for index in self.indices:
            self.total_interviews[index].exceptions.print()

    def get_updates(self):
        """Return a list of all the updates."""
        updates = []
        for interview in self.total_interviews:
            for question_name, logs in interview.task_status_logs.items():
                updates.append(logs)
        return updates

    def plot_completion_times(self):
        """Plot the completion times for each task."""
        updates = self.get_updates()

        elapsed = [update.max_time - update.min_time for update in updates]
        for i, update in enumerate(updates):
            if update[-1]["value"] != TaskStatus.SUCCESS:
                elapsed[i] = 0
        x = range(len(elapsed))
        y = elapsed

        plt.bar(x, y)
        plt.title("Per-interview completion times")
        plt.xlabel("Task")
        plt.ylabel("Time (seconds)")
        plt.show()

    def plotting_data(self, num_periods=100):
        updates = self.get_updates()

        min_t = min([update.min_time for update in updates])
        max_t = max([update.max_time for update in updates])
        delta_t = (max_t - min_t) / (num_periods * 1.0)
        time_periods = [min_t + delta_t * i for i in range(num_periods)]

        def counts(t):
            d = {}
            for update in updates:
                status = update.status_at_time(t)
                if status in d:
                    d[status] += 1
                else:
                    d[status] = 1
            return d

        status_counts = [counts(t) for t in time_periods]

        new_counts = []
        for status_count in status_counts:
            d = {task_status: 0 for task_status in TaskStatus}
            d.update(status_count)
            new_counts.append(d)

        return new_counts

    def plot(self, num_periods=100):
        """Plot the number of tasks in each state over time."""
        new_counts = self.plotting_data(num_periods)
        max_count = max([max(entry.values()) for entry in new_counts])

        rows = int(len(TaskStatus) ** 0.5) + 1
        cols = (len(TaskStatus) + rows - 1) // rows  # Ensure all plots fit
        from matplotlib import pyplot as plt

        plt.figure(figsize=(15, 10))  # Adjust the figure size as needed
        for i, status in enumerate(TaskStatus, start=1):
            plt.subplot(rows, cols, i)
            x = range(len(new_counts))
            y = [
                item.get(status, 0) for item in new_counts
            ]  # Use .get() to handle missing keys safely
            plt.plot(x, y, marker="o", linestyle="-")
            plt.title(status.name)
            plt.xlabel("Time Periods")
            plt.ylabel("Count")
            plt.grid(True)
            plt.ylim(0, max_count)

        plt.tight_layout()
        plt.show()
