from edsl.jobs.JobsRunnerSerial import JobsRunnerSerial
from edsl.jobs.JobsRunnerThreaded import JobsRunnerThreaded

JobsRunnersRegistry = {
    "serial": JobsRunnerSerial,
    "threaded": JobsRunnerThreaded,
}
