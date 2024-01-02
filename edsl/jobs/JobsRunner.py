from __future__ import annotations
from abc import ABC, abstractmethod
from edsl.jobs import Jobs
from edsl.results import Results


class JobsRunner(ABC):
    """ABC for JobRunners, which take in a job, conduct interviews, and return their results."""

    def __init__(self, jobs: Jobs):
        self.jobs = jobs
        # create the interviews here so children can use them
        self.interviews = jobs.interviews()

    @abstractmethod
    def run(
        self,
        n: int = 1,
        debug: bool = False,
        verbose: bool = False,
        progress_bar: bool = True,
    ) -> Results:  # pragma: no cover
        """
        Runs the job: conducts Interviews and returns their results.
        - `n`: how many times to run each interview
        - `debug`: prints debug messages
        - `verbose`: prints messages
        - `progress_bar`: shows a progress bar
        """
        raise NotImplementedError
