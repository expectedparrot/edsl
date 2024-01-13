from edsl.jobs.JobsRunnerSerial import JobsRunnerSerial
from edsl.jobs.JobsRunnerThreaded import JobsRunnerThreaded
from edsl.jobs.JobsRunnerStreaming import JobsRunnerStreaming
from edsl.jobs.JobsRunnerAsyncio import JobsRunnerAsyncio

JobsRunnersRegistry = {
    "serial": JobsRunnerSerial,
    "streaming": JobsRunnerStreaming,
    "threaded": JobsRunnerThreaded,
    "asyncio": JobsRunnerAsyncio,
}
