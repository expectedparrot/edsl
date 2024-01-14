from __future__ import annotations

from abc import ABC, ABCMeta, abstractmethod
from edsl.jobs import Jobs
from edsl.results import Results


class RegisterJobsRunnerMeta(ABCMeta):
    "Metaclass to register output elements in a registry i.e., those that have a parent"
    _registry = {}  # Initialize the registry as a dictionary

    def __init__(cls, name, bases, dct):
        super(RegisterJobsRunnerMeta, cls).__init__(name, bases, dct)
        if name != "JobsRunner":
            RegisterJobsRunnerMeta._registry[name] = cls

    @classmethod
    def get_registered_classes(cls):
        return cls._registry

    @classmethod
    def lookup(cls):
        d = {}
        for classname, cls in cls._registry.items():
            if hasattr(cls, "runner_name"):
                d[cls.runner_name] = cls
            else:
                raise Exception(
                    f"Class {classname} does not have a runner_name attribute"
                )
        return d


class JobsRunner(ABC, metaclass=RegisterJobsRunnerMeta):
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
