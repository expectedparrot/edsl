from __future__ import annotations
import time
import asyncio
import threading
from typing import Coroutine, List, AsyncGenerator, Optional, Union, Generator
from contextlib import contextmanager
from collections import UserList

from edsl.results.Results import Results
from edsl.jobs.interviews.Interview import Interview
from edsl.jobs.runners.JobsRunnerStatus import JobsRunnerStatus

from edsl.jobs.tasks.TaskHistory import TaskHistory
from edsl.jobs.buckets.BucketCollection import BucketCollection
from edsl.utilities.decorators import jupyter_nb_handler
from edsl.data.Cache import Cache
from edsl.results.Result import Result
from edsl.results.Results import Results
from edsl.language_models.LanguageModel import LanguageModel
from edsl.data.Cache import Cache

class StatusTracker(UserList):
    def __init__(self, total_tasks: int):
        self.total_tasks = total_tasks
        super().__init__()

    def current_status(self):
        return print(f"Completed: {len(self.data)} of {self.total_tasks}", end="\r")


class JobsRunnerAsyncio:
    """A class for running a collection of interviews asynchronously.

    It gets instaniated from a Jobs object.
    The Jobs object is a collection of interviews that are to be run.
    """

    def __init__(self, jobs: "Jobs"):
        self.jobs = jobs
        self.interviews: List["Interview"] = jobs.interviews()
        self.bucket_collection: "BucketCollection" = jobs.bucket_collection
        self.total_interviews: List["Interview"] = []

    async def run_async_generator(
        self,
        cache: Cache,
        n: int = 1,
        stop_on_exception: bool = False,
        sidecar_model: Optional[LanguageModel] = None,
        total_interviews: Optional[List["Interview"]] = None,
        raise_validation_errors: bool = False,
    ) -> AsyncGenerator["Result", None]:
        """Creates the tasks, runs them asynchronously, and returns the results as a Results object.

        Completed tasks are yielded as they are completed.

        :param n: how many times to run each interview
        :param stop_on_exception: Whether to stop the interview if an exception is raised
        :param sidecar_model: a language model to use in addition to the interview's model
        :param total_interviews: A list of interviews to run can be provided instead.
        :param raise_validation_errors: Whether to raise validation errors
        """
        tasks = []
        if total_interviews:  # was already passed in total interviews
            self.total_interviews = total_interviews
        else:
            self.total_interviews = list(
                self._populate_total_interviews(n=n)
            )  # Populate self.total_interviews before creating tasks

        for interview in self.total_interviews:
            interviewing_task = self._build_interview_task(
                interview=interview,
                stop_on_exception=stop_on_exception,
                sidecar_model=sidecar_model,
                raise_validation_errors=raise_validation_errors,
            )
            tasks.append(asyncio.create_task(interviewing_task))

        for task in asyncio.as_completed(tasks):
            result = await task
            self.jobs_runner_status.add_completed_interview(result)
            yield result

    def _populate_total_interviews(
        self, n: int = 1
    ) -> Generator["Interview", None, None]:
        """Populates self.total_interviews with n copies of each interview.

        :param n: how many times to run each interview.
        """
        for interview in self.interviews:
            for iteration in range(n):
                if iteration > 0:
                    yield interview.duplicate(iteration=iteration, cache=self.cache)
                else:
                    interview.cache = self.cache
                    yield interview

    async def run_async(self, cache: Optional[Cache] = None, n: int = 1) -> Results:
        """Used for some other modules that have a non-standard way of running interviews."""
        self.jobs_runner_status = JobsRunnerStatus(self, n=n)
        self.cache = Cache() if cache is None else cache
        data = []
        async for result in self.run_async_generator(cache=self.cache, n=n):
            data.append(result)
        return Results(survey=self.jobs.survey, data=data)

    def simple_run(self):
        data = asyncio.run(self.run_async())
        return Results(survey=self.jobs.survey, data=data)

    async def _build_interview_task(
        self,
        *,
        interview: Interview,
        stop_on_exception: bool = False,
        sidecar_model: Optional["LanguageModel"] = None,
        raise_validation_errors: bool = False,
    ) -> "Result":
        """Conducts an interview and returns the result.

        :param interview: the interview to conduct
        :param stop_on_exception: stops the interview if an exception is raised
        :param sidecar_model: a language model to use in addition to the interview's model
        """
        # the model buckets are used to track usage rates
        model_buckets = self.bucket_collection[interview.model]

        # get the results of the interview
        answer, valid_results = await interview.async_conduct_interview(
            model_buckets=model_buckets,
            stop_on_exception=stop_on_exception,
            sidecar_model=sidecar_model,
            raise_validation_errors=raise_validation_errors,
        )

        question_results = {}
        for result in valid_results:
            question_results[result.question_name] = result

        answer_key_names = list(question_results.keys())

        generated_tokens_dict = {
            k + "_generated_tokens": question_results[k].generated_tokens
            for k in answer_key_names
        }
        comments_dict = {
            k + "_comment": question_results[k].comment for k in answer_key_names
        }

        # we should have a valid result for each question
        answer_dict = {k: answer[k] for k in answer_key_names}
        assert len(valid_results) == len(answer_key_names)

        # TODO: move this down into Interview
        question_name_to_prompts = dict({})
        for result in valid_results:
            question_name = result.question_name
            question_name_to_prompts[question_name] = {
                "user_prompt": result.prompts["user_prompt"],
                "system_prompt": result.prompts["system_prompt"],
            }

        prompt_dictionary = {}
        for answer_key_name in answer_key_names:
            prompt_dictionary[answer_key_name + "_user_prompt"] = (
                question_name_to_prompts[answer_key_name]["user_prompt"]
            )
            prompt_dictionary[answer_key_name + "_system_prompt"] = (
                question_name_to_prompts[answer_key_name]["system_prompt"]
            )

        raw_model_results_dictionary = {}
        cache_used_dictionary = {}
        for result in valid_results:
            question_name = result.question_name
            raw_model_results_dictionary[question_name + "_raw_model_response"] = (
                result.raw_model_response
            )
            raw_model_results_dictionary[question_name + "_cost"] = result.cost
            one_use_buys = (
                "NA"
                if isinstance(result.cost, str)
                or result.cost == 0
                or result.cost is None
                else 1.0 / result.cost
            )
            raw_model_results_dictionary[question_name + "_one_usd_buys"] = one_use_buys
            cache_used_dictionary[question_name] = result.cache_used

        result = Result(
            agent=interview.agent,
            scenario=interview.scenario,
            model=interview.model,
            iteration=interview.iteration,
            answer=answer_dict,
            prompt=prompt_dictionary,
            raw_model_response=raw_model_results_dictionary,
            survey=interview.survey,
            generated_tokens=generated_tokens_dict,
            comments_dict=comments_dict,
            cache_used_dict=cache_used_dictionary,
        )
        result.interview_hash = hash(interview)

        return result

    @property
    def elapsed_time(self):
        return time.monotonic() - self.start_time

    def process_results(
        self, raw_results: Results, cache: Cache, print_exceptions: bool
    ):
        interview_lookup = {
            hash(interview): index
            for index, interview in enumerate(self.total_interviews)
        }
        interview_hashes = list(interview_lookup.keys())

        task_history = TaskHistory(self.total_interviews, include_traceback=False)

        results = Results(
            survey=self.jobs.survey,
            data=sorted(
                raw_results, key=lambda x: interview_hashes.index(x.interview_hash)
            ),
            task_history=task_history,
            cache=cache,
        )
        results.bucket_collection = self.bucket_collection

        if results.has_unfixed_exceptions and print_exceptions:
            from edsl.scenarios.FileStore import HTMLFileStore
            from edsl.config import CONFIG
            from edsl.coop.coop import Coop

            msg = f"Exceptions were raised in {len(results.task_history.indices)} out of {len(self.total_interviews)} interviews.\n"

            if len(results.task_history.indices) > 5:
                msg += f"Exceptions were raised in the following interviews: {results.task_history.indices}.\n"

            print(msg)
            # this is where exceptions are opening up
            filepath = results.task_history.html(
                cta="Open report to see details.",
                open_in_browser=True,
                return_link=True,
            )

            try:
                coop = Coop()
                user_edsl_settings = coop.edsl_settings
                remote_logging = user_edsl_settings["remote_logging"]
            except Exception as e:
                print(e)
                remote_logging = False

            if remote_logging:
                filestore = HTMLFileStore(filepath)
                coop_details = filestore.push(description="Error report")
                print(coop_details)

            print("Also see: https://docs.expectedparrot.com/en/latest/exceptions.html")

        return results

    @jupyter_nb_handler
    async def run(
        self,
        cache: Union[Cache, False, None],
        n: int = 1,
        stop_on_exception: bool = False,
        progress_bar: bool = False,
        sidecar_model: Optional[LanguageModel] = None,
        print_exceptions: bool = True,
        raise_validation_errors: bool = False,
    ) -> "Coroutine":
        """Runs a collection of interviews, handling both async and sync contexts."""

        self.results = []
        self.start_time = time.monotonic()
        self.completed = False
        self.cache = cache
        self.sidecar_model = sidecar_model

        self.jobs_runner_status = JobsRunnerStatus(self, n=n)

        stop_event = threading.Event()

        async def process_results(cache):
            """Processes results from interviews."""
            async for result in self.run_async_generator(
                n=n,
                stop_on_exception=stop_on_exception,
                cache=cache,
                sidecar_model=sidecar_model,
                raise_validation_errors=raise_validation_errors,
            ):
                self.results.append(result)
            self.completed = True

        def run_progress_bar(stop_event):
            """Runs the progress bar in a separate thread."""
            self.jobs_runner_status.update_progress(stop_event)

        if progress_bar:
            progress_thread = threading.Thread(
                target=run_progress_bar, args=(stop_event,)
            )
            progress_thread.start()

        exception_to_raise = None
        try:
            with cache as c:
                await process_results(cache=c)
        except KeyboardInterrupt:
            print("Keyboard interrupt received. Stopping gracefully...")
            stop_event.set()
        except Exception as e:
            if stop_on_exception:
                exception_to_raise = e
            stop_event.set()
        finally:
            stop_event.set()
            if progress_bar:
                # self.jobs_runner_status.stop_event.set()
                if progress_thread:
                    progress_thread.join()

            if exception_to_raise:
                raise exception_to_raise

            return self.process_results(
                raw_results=self.results, cache=cache, print_exceptions=print_exceptions
            )
