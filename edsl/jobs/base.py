from collections import UserDict

from edsl.jobs.JobsRunnerSerial import JobsRunnerSerial
from edsl.jobs.JobsRunnerThreaded import JobsRunnerThreaded
from edsl.jobs.JobsRunnerStreaming import JobsRunnerStreaming
from edsl.jobs.JobsRunnerAsyncio import JobsRunnerAsyncio
from edsl.jobs.JobsRunnerDryRun import JobsRunnerDryRun

from edsl.exceptions import JobsRunError


class JobsRunnersRegistryDict(UserDict):
    def __getitem__(self, key):
        try:
            return super().__getitem__(key)
        except KeyError:
            raise JobsRunError(f"JobsRunner '{key}' not found in registry.")


registry_data = {
    "serial": JobsRunnerSerial,
    "streaming": JobsRunnerStreaming,
    "threaded": JobsRunnerThreaded,
    "asyncio": JobsRunnerAsyncio,
    "dryrun": JobsRunnerDryRun,
}

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
        return instance.__dict__[self.name]

    def __set__(self, instance, value: str) -> None:
        self.validate(value, instance)
        if value == "serial":
            print("Warning: This is slow. Consider using a different JobsRunner.")
        if value == "threaded":
            print("Warning: This is deprecated. Consider using 'asyncio' as the method")
        instance.__dict__[self.name] = value

    def __set_name__(self, owner, name: str) -> None:
        self.name = "_" + name
