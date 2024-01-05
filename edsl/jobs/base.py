from edsl.jobs.JobsRunnerSerial import JobsRunnerSerial
from edsl.jobs.JobsRunnerThreaded import JobsRunnerThreaded
from edsl.jobs.JobsRunnerStreaming import JobsRunnerStreaming

JobsRunnersRegistry = {
    "serial": JobsRunnerSerial,
    "streaming": JobsRunnerStreaming,
    "threaded": JobsRunnerThreaded,
}
