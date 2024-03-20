"""Base module for JobsRunners."""
from collections import UserDict
import importlib

from edsl.jobs.runners.JobsRunnerAsyncio import JobsRunnerAsyncio
from edsl.jobs.runners.JobsRunnerDryRun import JobsRunnerDryRun

from edsl.exceptions import JobsRunError
from edsl.jobs.JobsRunner import RegisterJobsRunnerMeta


class JobsRunnersRegistryDict(UserDict):
    """A dictionary of JobsRunners."""

    def __getitem__(self, key):
        """Get the item from the dictionary. If it does not exist, raise an exception."""
        try:
            return super().__getitem__(key)
        except KeyError:
            raise JobsRunError(f"JobsRunner '{key}' not found in registry.")


registry_data = RegisterJobsRunnerMeta.lookup()
JobsRunnersRegistry = JobsRunnersRegistryDict(registry_data)


class JobsRunnerDescriptor:
    """Descriptor for a JobsRunner."""

    def validate(self, value: str) -> None:
        """Validate the value. If it is invalid, raise an exception. If it is valid, do nothing."""
        if value not in JobsRunnersRegistry:
            raise ValueError(
                f"JobsRunner must be one of {list(JobsRunnersRegistry.keys())}"
            )

    def __get__(self, instance, owner):
        """Get the value of the descriptor."""
        if self.name not in instance.__dict__:
            return None
        else:
            return instance.__dict__[self.name]

    def __set__(self, instance, value: str) -> None:
        """Set the value of the descriptor. Validate the value first."""
        self.validate(value, instance)
        instance.__dict__[self.name] = value

    def __set_name__(self, owner, name: str) -> None:
        """Set the name of the descriptor."""
        self.name = "_" + name


if __name__ == "__main__":
    pass
