import asyncio

from edsl.jobs import Jobs
from edsl.results import Results, Result
from edsl.jobs.JobsRunner import JobsRunner


class JobsRunnerDryRun(JobsRunner):
    runner_name = "dryrun"

    def __init__(self, jobs: Jobs):
        super().__init__(jobs)

    def run(
        self, n=1, verbose=False, sleep=0, debug=False, progress_bar=False
    ) -> Results:
        """Runs a collection of interviews."""

        print(f"This will run {len(self.interviews)} interviews.")
