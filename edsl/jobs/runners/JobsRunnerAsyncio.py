from __future__ import annotations
import time
import asyncio
import time
from contextlib import contextmanager

from typing import Coroutine, List, AsyncGenerator, Optional, Union

from edsl import shared_globals
from edsl.jobs.interviews.Interview import Interview
from edsl.jobs.runners.JobsRunnerStatusMixin import JobsRunnerStatusMixin
from edsl.jobs.tasks.TaskHistory import TaskHistory
from edsl.jobs.buckets.BucketCollection import BucketCollection
from edsl.utilities.decorators import jupyter_nb_handler

#from queue import Queue
from collections import UserList

class StatusTracker(UserList):
    def __init__(self, total_tasks: int):
        self.total_tasks = total_tasks
        super().__init__()
    
    def current_status(self):
        return print(f"Completed: {len(self.data)} of {self.total_tasks}", end = "\r")

class JobsRunnerAsyncio(JobsRunnerStatusMixin):
    """A class for running a collection of interviews asynchronously.

    It gets instaniated from a Jobs object.
    The Jobs object is a collection of interviews that are to be run.
    """

    def __init__(self, jobs: Jobs):
        self.jobs = jobs
        # this creates the interviews, which can take a while
        self.interviews: List["Interview"] = jobs.interviews()
        self.bucket_collection: "BucketCollection" = jobs.bucket_collection
        self.total_interviews: List["Interview"] = []

    async def run_async_generator(
        self,
        cache: "Cache",
        n: int = 1,
        debug: bool = False,
        stop_on_exception: bool = False,
        sidecar_model: "LanguageModel" = None,
        total_interviews: Optional[List["Interview"]] = None,
    ) -> AsyncGenerator["Result", None]:
        """Creates the tasks, runs them asynchronously, and returns the results as a Results object.

        Completed tasks are yielded as they are completed.

        :param n: how many times to run each interview
        :param debug:
        :param stop_on_exception: Whether to stop the interview if an exception is raised
        :param sidecar_model: a language model to use in addition to the interview's model
        :param total_interviews: A list of interviews to run can be provided instead.
        """
        tasks = []
        if total_interviews:
            self.total_interviews = total_interviews
        else:
            self._populate_total_interviews(
                n=n
            )  # Populate self.total_interviews before creating tasks

        for interview in self.total_interviews:
            interviewing_task = self._build_interview_task(
                interview=interview,
                debug=debug,
                stop_on_exception=stop_on_exception,
                sidecar_model=sidecar_model,
            )
            tasks.append(asyncio.create_task(interviewing_task))

        for task in asyncio.as_completed(tasks):
            result = await task
            yield result

    def _populate_total_interviews(self, n: int = 1) -> None:
        """Populates self.total_interviews with n copies of each interview.

        :param n: how many times to run each interview.
        """
        # TODO: Why not return a list of interviews instead of modifying the object?

        self.total_interviews = []
        for interview in self.interviews:
            for iteration in range(n):
                if iteration > 0:
                    new_interview = interview.duplicate(
                        iteration=iteration, cache=self.cache
                    )
                    self.total_interviews.append(new_interview)
                else:
                    interview.cache = (
                        self.cache
                    )  # set the cache for the first interview
                    self.total_interviews.append(interview)

    async def run_async(self, cache=None) -> Results:
        from edsl.results.Results import Results

        #breakpoint()
        #tracker = StatusTracker(total_tasks=len(self.interviews))

        if cache is None:
            self.cache = Cache()
        else:
            self.cache = cache
        data = []
        async for result in self.run_async_generator(cache=self.cache):
            data.append(result)
        return Results(survey=self.jobs.survey, data=data)

    def simple_run(self):
        from edsl.results.Results import Results

        data = asyncio.run(self.run_async())
        return Results(survey=self.jobs.survey, data=data)

    async def _build_interview_task(
        self,
        *,
        interview: Interview,
        debug: bool,
        stop_on_exception: bool = False,
        sidecar_model: Optional[LanguageModel] = None,
    ) -> Result:
        """Conducts an interview and returns the result.

        :param interview: the interview to conduct
        :param debug: prints debug messages
        :param stop_on_exception: stops the interview if an exception is raised
        :param sidecar_model: a language model to use in addition to the interview's model
        """
        # the model buckets are used to track usage rates
        model_buckets = self.bucket_collection[interview.model]

        # get the results of the interview
        answer, valid_results = await interview.async_conduct_interview(
            debug=debug,
            model_buckets=model_buckets,
            stop_on_exception=stop_on_exception,
            sidecar_model=sidecar_model,
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

        from edsl.results.Result import Result

        result = Result(
            agent=interview.agent,
            scenario=interview.scenario,
            model=interview.model,
            iteration=interview.iteration,
            answer=answer,
            prompt=prompt_dictionary,
            raw_model_response=raw_model_results_dictionary,
            survey=interview.survey,
        )
        return result

    @property
    def elapsed_time(self):
        return time.monotonic() - self.start_time

    @jupyter_nb_handler
    async def run(
        self,
        cache: Union[Cache, False, None],
        n: int = 1,
        debug: bool = False,
        stop_on_exception: bool = False,
        progress_bar: bool = False,
        sidecar_model: Optional[LanguageModel] = None,
        print_exceptions: bool = True,
    ) -> "Coroutine":
        """Runs a collection of interviews, handling both async and sync contexts."""
        from rich.console import Console

        console = Console()
        self.results = []
        self.start_time = time.monotonic()
        self.completed = False
        self.cache = cache
        self.sidecar_model = sidecar_model

        from edsl.results.Results import Results
        from rich.live import Live
        from rich.console import Console

        def generate_table():
            return self.status_table(self.results, self.elapsed_time)

        async def process_results(cache, progress_bar_context = None):
            """Processes results from interviews."""
            async for result in self.run_async_generator(
                n=n,
                debug=debug,
                stop_on_exception=stop_on_exception,
                cache=cache,
                sidecar_model=sidecar_model,
            ):
                self.results.append(result)
                if progress_bar_context:
                    progress_bar_context.update(generate_table())
                self.completed = True

        async def update_progress_bar(progress_bar_context):
            """Updates the progress bar at fixed intervals."""
            if progress_bar_context is None:
                return

            while True:
                progress_bar_context.update(generate_table())
                await asyncio.sleep(0.00001)  # Update interval
                if self.completed:
                    break

        @contextmanager
        def conditional_context(condition, context_manager):
            if condition:
                with context_manager as cm:
                    yield cm
            else:
                yield

        with conditional_context(progress_bar, Live(generate_table(), console=console, refresh_per_second=5)) as progress_bar_context:

            with cache as c:

                progress_task = asyncio.create_task(update_progress_bar(progress_bar_context))

                try:
                    await asyncio.gather(process_results(cache = c, progress_bar_context = progress_bar_context), progress_task)
                except asyncio.CancelledError:
                        pass
                finally:
                    progress_task.cancel()  # Cancel the progress_task when process_results is done
                    await progress_task

                    await asyncio.sleep(1)  # short delay to show the final status

                    if progress_bar_context:
                        progress_bar_context.update(generate_table())


        results = Results(survey=self.jobs.survey, data=self.results)
        task_history = TaskHistory(self.total_interviews, include_traceback=False)
        results.task_history = task_history

        results.has_exceptions = task_history.has_exceptions

        if results.has_exceptions:
            failed_interviews = [
                interview.duplicate(
                    iteration=interview.iteration, cache=interview.cache
                )
                for interview in self.total_interviews
                if interview.has_exceptions
            ]
            from edsl.jobs.Jobs import Jobs

            results.failed_jobs = Jobs.from_interviews(
                [interview for interview in failed_interviews]
            )
            if print_exceptions:
                msg = f"Exceptions were raised in {len(results.task_history.indices)} out of {len(self.total_interviews)} interviews.\n"

                if len(results.task_history.indices) > 5:
                    msg += f"Exceptions were raised in the following interviews: {results.task_history.indices}.\n"

                shared_globals["edsl_runner_exceptions"] = task_history
                print(msg)
                task_history.html(cta="Open report to see details.")
                print(
                    "Also see: https://docs.expectedparrot.com/en/latest/exceptions.html"
                )

        return results
