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
        answer, valid_results = await interview.async_conduct_interview(debug=debug)

        answer_key_names = {k for k in set(answer.keys()) if not k.endswith("_comment")}

        assert len(valid_results) == len(answer_key_names)

        question_name_to_prompts = dict({})
        for result in valid_results:
            question_name = result["question_name"]
            question_name_to_prompts[question_name] = {
                "user_prompt": result["prompts"]["user_prompt"],
                "system_prompt": result["prompts"]["system_prompt"],
            }

        prompt_dictionary = {}
        for answer_key_name in answer_key_names:
            prompt_dictionary[
                answer_key_name + "_user_prompt"
            ] = question_name_to_prompts[answer_key_name]["user_prompt"]
            prompt_dictionary[
                answer_key_name + "_system_prompt"
            ] = question_name_to_prompts[answer_key_name]["system_prompt"]

        # breakpoint()
        #        user_prompt = [for key in answer_key_names]
        # user_prompts, system_prompts = self._get_prompts(answer, prompt_data)
        # breakpoint()

        result = Result(
            agent=interview.agent,
            scenario=interview.scenario,
            model=interview.model,
            iteration=i,
            answer=answer,
            prompt=prompt_dictionary,
        )
        return result

    @jupyter_nb_handler
    def run(
        self, n=1, verbose=False, sleep=0, debug=False, progress_bar=False
    ) -> Coroutine:
        """Runs a collection of interviews, handling both async and sync contexts."""
        return self.run_async(n, verbose, sleep, debug, progress_bar)
