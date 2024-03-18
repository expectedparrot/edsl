import time
import asyncio
from typing import Coroutine, List, AsyncGenerator

from rich.live import Live
from rich.console import Console

from edsl.results import Results, Result
from edsl.jobs.runners.JobsRunner import JobsRunner
from edsl.jobs.interviews.Interview import Interview
from edsl.utilities.decorators import jupyter_nb_handler

from edsl.jobs.runners.JobsRunnerStatusMixin import JobsRunnerStatusMixin
from edsl.jobs.runners.JobsRunHistory import JobsRunHistory


class JobsRunnerAsyncio(JobsRunner, JobsRunnerStatusMixin):
    runner_name = "asyncio"
    job_history_tracker = JobsRunHistory()

    async def periodic_logger(self, period=1):
        """Logs every 'period' seconds.
        """
        self.job_history_tracker.log(self, self.results, self.elapsed_time)
        while True:
            await asyncio.sleep(period)  # Sleep for the specified period
            self.job_history_tracker.log(self, self.results, self.elapsed_time)
   
    async def run_async(
        self, 
        n: int = 1, 
        debug:bool = False, 
        stop_on_exception: bool = False,
    ) -> AsyncGenerator[Result, None]:
        """Creates the tasks, runs them asynchronously, and returns the results as a Results object.

        Completed tasks are yielded as they are completed.

        :param n: how many times to run each interview
        :param debug: 
        :param stop_on_exception:
        """
        tasks = []
        self.populate_total_interviews(n=n)  # Populate self.total_interviews before creating tasks

        for interview in self.total_interviews:
            interviewing_task = self._interview_task(interview=interview, debug=debug, stop_on_exception=stop_on_exception)
            tasks.append(asyncio.create_task(interviewing_task))

        for task in asyncio.as_completed(tasks):
            result = await task
            yield result

    async def _interview_task(self, *, interview: Interview, debug: bool, stop_on_exception:bool = False) -> Result:
        """Conducts an interview and returns the result.
        
        :param interview: the interview to conduct
        :param debug: prints debug messages
        """
        # the model buckets are used to track usage rates
        model_buckets = self.bucket_collection[interview.model]

        # get the results of the interview
        answer, valid_results = await interview.async_conduct_interview(
            debug=debug,
            model_buckets=model_buckets,
            stop_on_exception=stop_on_exception,
        )

        # we should have a valid result for each question
        answer_key_names = {k for k in set(answer.keys()) if not k.endswith("_comment")}

        assert len(valid_results) == len(answer_key_names)


        # TODO: move this down into Interview
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

    @property
    def elapsed_time(self):
        return time.monotonic() - self.start_time

    @jupyter_nb_handler
    async def run(
        self, 
        n:int =1, 
        debug:bool =False, 
        stop_on_exception:bool = False,
        progress_bar=False, 
    ) -> Coroutine:
        """Runs a collection of interviews, handling both async and sync contexts.
        
        :param n: how many times to run each interview
        :param verbose: prints messages
        :param sleep: how long to sleep between interviews
        :param debug: prints debug messages
        """
        console = Console()
        self.results = []
        self.start_time = time.monotonic()
   
        ## TODO: 
        ## - factor out the debug in run_async
        ## - Add a "break on error" option

        live = None
        if progress_bar:
            live = Live(
                self.status_table(self.results, elapsed_time = 0),
                console=console,
                refresh_per_second=10,
            )
            live.__enter__()  # Manually enter the Live context

        logger_task = asyncio.create_task(self.periodic_logger(period = 0.01))
             
        async for result in self.run_async(n = n, debug = debug, stop_on_exception = stop_on_exception):
        
            self.results.append(result)
        
            if progress_bar:
                live.update(self.status_table(self.results, self.elapsed_time))

        if progress_bar:
            live.update(self.status_table(self.results, self.elapsed_time))
            await asyncio.sleep(0.5)  # short delay to show the final status
            live.__exit__(None, None, None)  # Manually exit the Live context

        if debug:
            print("Debug data saved to debug_data.json.")

        logger_task.cancel()
        try:
            await logger_task  # Wait for the cancellation to complete, catching any cancellation errors
        except asyncio.CancelledError:
            pass

        results = Results(survey=self.jobs.survey, data=self.results)
        results.job_history_tracker = self.job_history_tracker
        return results