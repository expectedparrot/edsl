import asyncio

from edsl.jobs import Jobs
from edsl.results import Results, Result
from edsl.jobs.JobsRunner import JobsRunner
from typing import Coroutine


from edsl.utilities.decorators import jupyter_nb_handler


class JobsRunnerAsyncio(JobsRunner):
    runner_name = "asyncio"

    def __init__(self, jobs: Jobs):
        super().__init__(jobs)

    async def run_async(
        self, n=1, verbose=False, sleep=0, debug=False, progress_bar=False
    ) -> Results:
        """Asynchronous method to run a collection of interviews."""

        async def process_task(interview, i):
            # Assuming async_conduct_interview and Result are defined and work asynchronously
            answer = await interview.async_conduct_interview(debug=debug)
            result = Result(
                agent=interview.agent,
                scenario=interview.scenario,
                model=interview.model,
                iteration=i,
                answer=answer,
            )
            return result

        async def main(interviews):
            tasks = [
                process_task(interview, i) for i, interview in enumerate(interviews)
            ]
            results = await asyncio.gather(*tasks)
            return results

        return Results(survey=self.jobs.survey, data=await main(self.interviews))

    @jupyter_nb_handler
    def run(
        self, n=1, verbose=False, sleep=0, debug=False, progress_bar=False
    ) -> Coroutine:
        """Runs a collection of interviews, handling both async and sync contexts."""
        return self.run_async(n, verbose, sleep, debug, progress_bar)
