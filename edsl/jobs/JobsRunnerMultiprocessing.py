import asyncio

from edsl.jobs import Jobs
from edsl.results import Results, Result
from edsl.jobs.JobsRunner import JobsRunner


class JobsRunnerMultiprocessing(JobsRunner):
    def __init__(self, jobs: Jobs):
        super().__init__(jobs)

    def run(
        self, n=1, verbose=False, sleep=0, debug=False, progress_bar=False
    ) -> Results:
        """Runs a collection of interviews."""

        async def process_task(interview, i):
            answer = await interview.conduct_interview(debug=debug)
            result = Result(
                survey=interview.survey,
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

        data = asyncio.run(main(self.interviews))
        return Results(survey=self.jobs.survey, data=data)
