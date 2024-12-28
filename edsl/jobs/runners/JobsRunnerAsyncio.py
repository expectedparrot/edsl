from __future__ import annotations
import time
import asyncio
import threading
import warnings
from typing import (
    Coroutine,
    List,
    Optional,
    Union,
    Type,
    TYPE_CHECKING,
)
from uuid import UUID
from collections import UserList

from edsl.results.Results import Results
from edsl.jobs.interviews.Interview import Interview
from edsl.jobs.runners.JobsRunnerStatus import JobsRunnerStatus, JobsRunnerStatusBase

from edsl.jobs.tasks.TaskHistory import TaskHistory
from edsl.jobs.buckets.BucketCollection import BucketCollection
from edsl.utilities.decorators import jupyter_nb_handler
from edsl.data.Cache import Cache

from edsl.jobs.async_interview_runner import AsyncInterviewRunner

if TYPE_CHECKING:
    from edsl.language_models.key_management.KeyLookup import KeyLookup
    from edsl.jobs.interviews import Interview


class JobsRunnerAsyncio:
    """A class for running a collection of interviews asynchronously.

    It gets instaniated from a Jobs object.
    The Jobs object is a collection of interviews that are to be run.
    """

    def __init__(
        self,
        jobs: "Jobs",
        bucket_collection: "BucketCollection",
        key_lookup: Optional[KeyLookup] = None,
        cache: Optional[Cache] = None,
    ):
        self.jobs = jobs

        self.cache = cache
        self.bucket_collection: "BucketCollection" = bucket_collection
        self.key_lookup = key_lookup

    @property
    def interviews(self):
        "Interviews associated with the job runner; still deprecate"
        import warnings

        warnings.warn("We are deprecating this!")
        return self.jobs.interviews()

    async def run_async(
        self,
        cache: Optional[Cache] = None,
        n: int = 1,
        stop_on_exception: bool = False,
        raise_validation_errors: bool = False,
        **kwargs,
    ) -> Results:
        """Used for some other modules that have a non-standard way of running interviews."""
        self.jobs_runner_status = JobsRunnerStatus(self, n=n)
        data = []
        self.n = n
        self.stop_on_exception = stop_on_exception
        self.raise_validation_errors = raise_validation_errors
        task_history = TaskHistory(include_traceback=False)

        result_generator = AsyncInterviewRunner(
            self.jobs,
            n=n,
            cache=cache,
            stop_on_exception=stop_on_exception,
            bucket_collection=self.bucket_collection,
            raise_validation_errors=raise_validation_errors,
            key_lookup=self.key_lookup,
            jobs_runner_status=self.jobs_runner_status,
        )

        async for result, interview in result_generator.run():
            data.append(result)
            task_history.add_interview(interview)

        return Results(survey=self.jobs.survey, task_history=task_history, data=data)

    def simple_run(self):
        data = asyncio.run(self.run_async())
        return Results(survey=self.jobs.survey, data=data)

    @jupyter_nb_handler
    async def run(
        self,
        cache: Union[Cache, False, None] = None,
        n: int = 1,
        stop_on_exception: bool = False,
        progress_bar: bool = False,
        print_exceptions: bool = True,
        raise_validation_errors: bool = False,
        jobs_runner_status: Optional[Type[JobsRunnerStatusBase]] = None,
        job_uuid: Optional[UUID] = None,
    ) -> "Coroutine":
        """Runs a collection of interviews, handling both async and sync contexts."""

        # results = []
        self.start_time = time.monotonic()
        self.completed = False
        # self.cache = cache

        if cache:
            # raise Exception("The cache parameter is not supported in this version.")
            warnings.warn("The cache parameter is not supported in this version.")

        from edsl.coop import Coop

        coop = Coop()
        endpoint_url = coop.get_progress_bar_url()

        self.n = n
        self.stop_on_exception = stop_on_exception
        self.progress_bar = progress_bar
        self.print_exceptions = print_exceptions
        self.raise_validation_errors = raise_validation_errors
        self.job_uuid = job_uuid

        def set_up_jobs_runner_status(jobs_runner_status):
            if jobs_runner_status is not None:
                return jobs_runner_status(
                    self, n=self.n, endpoint_url=endpoint_url, job_uuid=self.job_uuid
                )
            else:
                return JobsRunnerStatus(
                    self, n=n, endpoint_url=endpoint_url, job_uuid=job_uuid
                )

        self.jobs_runner_status = set_up_jobs_runner_status(jobs_runner_status)

        async def get_results(results) -> None:
            """Conducted the interviews and append to the results list."""
            result_generator = AsyncInterviewRunner(
                self.jobs,
                n=n,
                cache=cache,
                stop_on_exception=stop_on_exception,
                bucket_collection=self.bucket_collection,
                raise_validation_errors=raise_validation_errors,
                key_lookup=self.key_lookup,
                jobs_runner_status=self.jobs_runner_status,
            )
            async for result, interview in result_generator.run():
                results.append(result)
                results.task_history.add_interview(interview)

            self.completed = True

        def run_progress_bar(stop_event) -> None:
            """Runs the progress bar in a separate thread."""
            self.jobs_runner_status.update_progress(stop_event)

        def set_up_progress_bar(progress_bar: bool, jobs_runner_status):
            progress_thread = None
            if progress_bar and jobs_runner_status.has_ep_api_key():
                jobs_runner_status.setup()
                progress_thread = threading.Thread(
                    target=run_progress_bar, args=(stop_event,)
                )
                progress_thread.start()
            elif progress_bar:
                warnings.warn(
                    "You need an Expected Parrot API key to view job progress bars."
                )
            return progress_thread

        results = Results(
            survey=self.jobs.survey,
            data=[],
            task_history=TaskHistory(),
            cache=self.cache.new_entries_cache(),
        )
        stop_event = threading.Event()
        progress_thread = set_up_progress_bar(progress_bar, self.jobs_runner_status)

        exception_to_raise = None
        try:
            await get_results(results)
        except KeyboardInterrupt:
            print("Keyboard interrupt received. Stopping gracefully...")
            stop_event.set()
        except Exception as e:
            if self.stop_on_exception:
                exception_to_raise = e
            stop_event.set()
        finally:
            stop_event.set()
            if progress_thread is not None:
                progress_thread.join()

            if exception_to_raise:
                raise exception_to_raise

            results.cache = self.cache.new_entries_cache()
            results.bucket_collection = self.bucket_collection
            self.handle_results_exceptions(results)
            return results

    def handle_results_exceptions(self, results: Results) -> None:
        """Prints exceptions and opens the exception report if necessary."""

        if results.has_unfixed_exceptions and self.print_exceptions:
            from edsl.scenarios.FileStore import HTMLFileStore
            from edsl.config import CONFIG
            from edsl.coop.coop import Coop

            msg = f"Exceptions were raised in {len(results.task_history.indices)} interviews.\n"

            if len(results.task_history.indices) > 5:
                msg += f"Exceptions were raised in the following interviews: {results.task_history.indices}.\n"

            import sys

            print(msg, file=sys.stderr)
            from edsl.config import CONFIG

            if CONFIG.get("EDSL_OPEN_EXCEPTION_REPORT_URL") == "True":
                open_in_browser = True
            elif CONFIG.get("EDSL_OPEN_EXCEPTION_REPORT_URL") == "False":
                open_in_browser = False
            else:
                raise Exception(
                    "EDSL_OPEN_EXCEPTION_REPORT_URL", "must be either True or False"
                )

            filepath = results.task_history.html(
                cta="Open report to see details.",
                open_in_browser=open_in_browser,
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
