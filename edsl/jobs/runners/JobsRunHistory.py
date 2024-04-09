from __future__ import annotations
import json
from typing import DefaultDict, Union, List
from collections import defaultdict

from edsl.jobs.interviews.InterviewStatusDictionary import InterviewStatusDictionary
from edsl.jobs.tokens.InterviewTokenUsage import InterviewTokenUsage
from edsl.jobs.tasks.task_status_enum import TaskStatus

# for type-hints
from edsl.jobs.runners.JobsRunner import JobsRunner
import asyncio

InterviewTokenUsageMapping = DefaultDict[str, InterviewTokenUsage]


class InterviewStatusObject:
    pass


class JobsRunHistory:
    """A class to store the history of jobs run.

    Each entry in JobsRunHistory is a tuple:
        - (time, JobStatus). The JobStatus is a list of:
            - InterviewStatus objects (1 per interview) which is a list of
                - Each InterviewStatus object has TaskStatus objects (1 per task)

    It's a list.
    The values is a list of the status updates of each the interviews, with time stamps.

    1. It should be a list of JobStatusObjects, with a time stamp.
    2. A JobStatus object should be a list of InterviewStatusObjects at that time.
    >>> [(time, JobStatusObject), (time, JobStatusObject), (time, JobStatusObject), ...]

    >>> {"interview1": [
        {"time": 0, "status": "InterviewStatusObject"},
        {"time": 1, "status": "InterviewStatusObject"},
        {"time": 2, "status": "InterviewStatusObject"},
        ...
        ],
        "interview2": [
        {"time": 0, "status": "InterviewStatusObject"},
        {"time": 1, "status": "InterviewStatusObject"},
        {"time": 2, "status": "InterviewStatusObject"},
        ...
        ]

    The status at a given time is what entry in the list closest to the asked-for time.

    InterviewStatusObject + InterviewStatusObject --> JobsRunStatusObject

    The goal of this class is to give a detailed history of the jobs run.

    -- Task failures and tracebacks
    -- Response headers from API calls
    -- Log each time an Interview is completed

    Methods:
    --- Visualization tools

    """

    def __init__(self, data: Union[dict, None] = None):
        """Create a new JobsRunHistory object."""
        self.data: dict = data or {}
        self.entries: int = 0
        self.status_functions = {
            "status_dic": self.status_dict,
            "status_counts": self.status_counts,
            "time": self.log_time,
            "exceptions": self.exceptions_dict,
        }

    def print(self):
        """Print the JobsRunHistory object."""
        for elapsed_time, index, status in self.data["status_dic"]:
            # breakpoint()
            print(f"Elapsed Time: {elapsed_time}, Interview index: {index}")
            for interview_status in status:
                interview_status.print()

    def log(
        self,
        JobsRunner: "JobsRunner",
        completed_tasks: List[asyncio.Task],
        elapsed_time: Union[int, float],
    ) -> None:
        """Log the status of the job runner.

        >>> jrh = JobsRunHistory()
        >>> from edsl.jobs.runners.JobsRunnerAsyncio import JobsRunnerAsyncio
        >>> from edsl.jobs.Jobs import Jobs
        >>> jr = JobsRunnerAsyncio(jobs = Jobs.example())
        >>> jrh.log(jr, [], 0)
        >>> jrh.entries
        1
        """

        self.entries += 1

        for name, f in self.status_functions.items():
            entry = f(JobsRunner, completed_tasks, elapsed_time)
            if name not in self.data:
                self.data[name] = []
            self.data[name].append(entry)

    def log_time(self, JobsRunner: "JobsRunner", completed_tasks, elapsed_time):
        return elapsed_time

    def status_dict(
        self, JobsRunner: "JobsRunner", completed_tasks, elapsed_time
    ) -> tuple:
        status = []
        index = -1
        for index, interview in enumerate(JobsRunner.total_interviews):
            status.append(interview.interview_status)
        return (elapsed_time, index, status)

    def exceptions_dict(self, JobsRunner, completed_tasks, elapsed_time) -> tuple:
        exceptions = []
        index = -1
        for index, interview in enumerate(JobsRunner.total_interviews):
            if interview.has_exceptions:
                exceptions.append(interview.exceptions)
        return (elapsed_time, index, exceptions)

    def status_counts(self, JobsRunner, completed_tasks, elapsed_time) -> tuple:
        model_to_status = defaultdict(InterviewStatusDictionary)
        index = -1
        interviews_counted = 0
        for index, interview in enumerate(JobsRunner.total_interviews):
            model = interview.model
            model_to_status[model] += interview.interview_status
            interviews_counted += 1
        assert interviews_counted == len(JobsRunner.total_interviews)
        return (elapsed_time, index, model_to_status)

    def to_dict(self) -> dict:
        d = {}
        for key, value in self.data.items():
            d[key] = [t for t in value]
        return d

    def to_json(self, json_file):
        with open(json_file, "w") as file:
            # json.dump(self.data, file, default=enum_converter)
            json.dump(obj=self.to_dict(), fp=file)

    @classmethod
    def from_json(cls, json_file):
        with open(json_file, "r") as file:
            data = json.load(file)
        return cls(data=data)

    def plot_completion_times(self):
        """Plot the completion times."""
        from matplotlib import pyplot as plt

        # x = [item for item in self.data['time']]

        status_counts = [
            (time, list(d.values())[0]) for time, index, d in self.data["status_counts"]
        ]
        status_counts.sort(key=lambda x: x[0])

        rows = int(len(TaskStatus) ** 0.5) + 1
        cols = (len(TaskStatus) + rows - 1) // rows  # Ensure all plots fit

        plt.figure(figsize=(15, 10))  # Adjust the figure size as needed
        for i, status in enumerate(TaskStatus, start=1):
            plt.subplot(rows, cols, i)
            x = [item[0] for item in status_counts]
            y = [
                item[1].get(status, 0) for item in status_counts
            ]  # Use .get() to handle missing keys safely
            plt.plot(x, y, marker="o", linestyle="-")
            plt.title(status.name)
            plt.xlabel("Elapsed Time")
            plt.ylabel("Count")
            plt.grid(True)

        plt.tight_layout()
        plt.show()


if __name__ == "__main__":
    # pass
    import doctest

    doctest.testmod()
