"""This module contains the JobsRunnerAsyncio class, which is used to run interviews asynchronously."""
import time
import asyncio
from typing import Coroutine, List, AsyncGenerator

from rich.live import Live
from rich.console import Console

from edsl.results import Results, Result
from edsl.jobs.JobsRunner import JobsRunner
from edsl.jobs.Interview import Interview
from edsl.utilities.decorators import jupyter_nb_handler

from edsl.jobs.JobsRunnerStatusMixin import JobsRunnerStatusMixin

class JobsRunnerAsyncio(JobsRunner, JobsRunnerStatusMixin):
    """An asyncio-based JobsRunner. This is the default runner for the EDSL. It is used to run interviews asynchronously."""

    runner_name = "asyncio"

    def populate_total_interviews(self, n = 1):
        """Populate self.total_interviews with the interviews to be conducted.
        
        This is used to run multiple iterations of the same interview.
        """
        self.total_interviews = []
        for interview in self.interviews:
            for iteration in range(n):
                if iteration > 0:
                    new_interview = Interview(
                        agent=interview.agent,
                        survey=interview.survey,
                        scenario=interview.scenario,
                        model=interview.model,
                        debug=interview.debug,
                        verbose=interview.verbose,
                        iteration=iteration,
                    )
                    self.total_interviews.append(new_interview)
                else:
                    self.total_interviews.append(interview)

    async def run_async(
        self, n=1, verbose=False, sleep=0, debug=False
    ) -> AsyncGenerator[Result, None]:
        """Create the tasks, runs them asynchronously, and returns the results as a Results object.
        
        Completed tasks are yielded as they are completed.
        """
        tasks = []
        self.populate_total_interviews(n=n)  # Populate self.total_interviews before creating tasks

        for interview in self.total_interviews:
            interviewing_task = self._interview_task(interview=interview, debug=debug)
            tasks.append(asyncio.create_task(interviewing_task))

        for task in asyncio.as_completed(tasks):
            result = await task
            yield result

    async def _interview_task(self, *, interview: Interview, debug: bool) -> Result:
        """Conduct an interview and returns the result."""
        # the model buckets are used to track usage rates
        model_buckets = self.bucket_collection[interview.model]

        # get the results of the interview
        answer, valid_results = await interview.async_conduct_interview(
            debug=debug,
            model_buckets=model_buckets,
        )

        # we should have a valid result for each question
        answer_key_names = {k for k in set(answer.keys()) if not k.endswith("_comment")}

        # TODO: Commenting out for now
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

        raw_model_results_dictionary = {}
        for result in valid_results:
            question_name = result["question_name"]
            raw_model_results_dictionary[
                question_name + "_raw_model_response"
            ] = result["raw_model_response"]

        result = Result(
            agent=interview.agent,
            scenario=interview.scenario,
            model=interview.model,
            iteration=interview.iteration,
            answer=answer,
            prompt=prompt_dictionary,
            raw_model_response=raw_model_results_dictionary,
        )
        return result

    @jupyter_nb_handler
    async def run(
        self, n=1, verbose=True, sleep=0, debug=False, progress_bar=False
    ) -> Coroutine:
        """Run a collection of interviews, handling both async and sync contexts."""
        verbose = True
        console = Console()
        data = []
        start_time = time.monotonic()

        live = None
        if progress_bar:
            live = Live(
                self.status_table(data, 0),
                console=console,
                refresh_per_second=10,
            )
            live.__enter__()  # Manually enter the Live context

        async for result in self.run_async(n, verbose, sleep, debug):
            end_time = time.monotonic()
            elapsed_time = end_time - start_time
            data.append(result)

            if progress_bar:
                live.update(self.status_table(data, elapsed_time))

        if progress_bar:
            live.update(self.status_table(data, elapsed_time))
            await asyncio.sleep(0.5)  # short delay to show the final status
            live.__exit__(None, None, None)  # Manually exit the Live context

        return Results(survey=self.jobs.survey, data=data)
