import asyncio
from typing import Coroutine, List
from edsl.results import Results, Result
from edsl.jobs.JobsRunner import JobsRunner
from edsl.utilities.decorators import jupyter_nb_handler


class JobsRunnerAsyncio(JobsRunner):
    runner_name = "asyncio"

    async def run_async(
        self, n=1, verbose=False, sleep=0, debug=False, progress_bar=False
    ) -> Results:
        """Creates the tasks, runs them asynchronously, and returns the results as a Results object."""

        tasks = self._create_all_interview_tasks(self.interviews, debug)
        data = await asyncio.gather(*tasks)
        return Results(survey=self.jobs.survey, data=data)

    def _create_all_interview_tasks(self, interviews, debug) -> List[asyncio.Task]:
        """Creates an awaitable task for each interview"""
        tasks = []
        for i, interview in enumerate(interviews):
            interviewing_task = self._interview_task(interview, i, debug)
            tasks.append(asyncio.create_task(interviewing_task))
        return tasks

    async def _interview_task(self, interview, i, debug):
        # Assuming async_conduct_interview and Result are defined and work asynchronously
        answer, prompt_data = await interview.async_conduct_interview(debug=debug)
        user_prompts, system_prompts = self._get_prompts(answer, prompt_data)
        # breakpoint()
        result = Result(
            agent=interview.agent,
            scenario=interview.scenario,
            model=interview.model,
            iteration=i,
            answer=answer,
            prompt=user_prompts | system_prompts,
        )
        return result

    def _get_prompts(self, answer, prompt_data):
        """Gets the prompts used in the survey."""
        answer_names = [k for k in answer.keys() if not k.endswith("_comment")]
        try:
            user_prompts = [result["prompts"]["user_prompt"] for result in prompt_data]
            system_prompts = [
                result["prompts"]["system_prompt"] for result in prompt_data
            ]
        except KeyError:
            user_prompts = [None] * len(answer_names)
            system_prompts = [None] * len(answer_names)

        def append_type(prompts, prompt_type):
            return {k + "_" + prompt_type: v for k, v in zip(answer_names, prompts)}

        user_prompts = append_type(user_prompts, "user_prompt")
        system_prompts = append_type(system_prompts, "system_prompt")

        return user_prompts, system_prompts

    @jupyter_nb_handler
    def run(
        self, n=1, verbose=False, sleep=0, debug=False, progress_bar=False
    ) -> Coroutine:
        """Runs a collection of interviews, handling both async and sync contexts."""
        return self.run_async(n, verbose, sleep, debug, progress_bar)
