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

    def get_prompts(self, results, answer):
        answer_names = [k for k in answer.keys() if not k.endswith("_comment")]
        try:
            user_prompts = [result["prompts"]["user_prompt"] for result in results]
            system_prompts = [result["prompts"]["system_prompt"] for result in results]
        except KeyError:
            user_prompts = [None] * len(answer_names)
            system_prompts = [None] * len(answer_names)

        def append_type(prompts, prompt_type):
            return {k + "_" + prompt_type: v for k, v in zip(answer_names, prompts)}

        user_prompts = append_type(user_prompts, "user_prompt")
        system_prompts = append_type(system_prompts, "system_prompt")

        return user_prompts, system_prompts

    async def run_async(
        self, n=1, verbose=False, sleep=0, debug=False, progress_bar=False
    ) -> Results:
        """Asynchronous method to run a collection of interviews."""

        async def process_task(interview, i):
            # Assuming async_conduct_interview and Result are defined and work asynchronously
            answer, results = await interview.async_conduct_interview(debug=debug)
            user_prompts, system_prompts = self.get_prompts(results, answer)
            result = Result(
                agent=interview.agent,
                scenario=interview.scenario,
                model=interview.model,
                iteration=i,
                answer=answer,
                prompt=user_prompts | system_prompts,
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
