from collections import UserDict
import importlib

from edsl.jobs.runners.JobsRunnerAsyncio import JobsRunnerAsyncio
from edsl.jobs.runners.JobsRunnerDryRun import JobsRunnerDryRun

from edsl.exceptions import JobsRunError
from edsl.jobs.JobsRunner import RegisterJobsRunnerMeta


class JobsRunnersRegistryDict(UserDict):
    def __getitem__(self, key):
        try:
            return super().__getitem__(key)
        except KeyError:
            raise JobsRunError(f"JobsRunner '{key}' not found in registry.")


registry_data = RegisterJobsRunnerMeta.lookup()
JobsRunnersRegistry = JobsRunnersRegistryDict(registry_data)


class JobsRunnerDescriptor:
    def validate(self, value: str) -> None:
        """Validates the value. If it is invalid, raises an exception. If it is valid, does nothing."""
        if value not in JobsRunnersRegistry:
            raise ValueError(
                f"JobsRunner must be one of {list(JobsRunnersRegistry.keys())}"
            )

    def __get__(self, instance, owner):
        """"""
        if self.name not in instance.__dict__:
            return None
        else:
            return instance.__dict__[self.name]

    def __set__(self, instance, value: str) -> None:
        self.validate(value, instance)
        instance.__dict__[self.name] = value

    def __set_name__(self, owner, name: str) -> None:
        self.name = "_" + name


if __name__ == "__main__":
    pass
