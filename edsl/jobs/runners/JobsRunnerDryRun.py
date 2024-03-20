"""A dry run of the jobs runner. This will not actually run the jobs, but will print out what would have been run."""
import asyncio

from edsl.jobs import Jobs
from edsl.results import Results, Result
from edsl.jobs.JobsRunner import JobsRunner


class JobsRunnerDryRun(JobsRunner):
    """A dry run of the jobs runner. This will not actually run the jobs, but will print out what would have been run."""

    runner_name = "dryrun"

    def __init__(self, jobs: Jobs):
        """Initialize the dry run jobs runner."""
        super().__init__(jobs)

    def run(
        self, n=1, verbose=False, sleep=0, debug=False, progress_bar=False
    ) -> Results:
        """Run a collection of interviews."""
        print(f"This will run {len(self.interviews)} interviews.")
