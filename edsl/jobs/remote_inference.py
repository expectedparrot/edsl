from typing import Optional, Union, Literal, TYPE_CHECKING, NewType, Callable, Any
from dataclasses import dataclass
from ..coop import CoopServerResponseError
from ..coop.utils import VisibilityType
from ..coop.coop import RemoteInferenceResponse, RemoteInferenceCreationInfo
from .jobs_status_enums import JobsStatus
from .jobs_remote_inference_logger import JobLogger
from .exceptions import RemoteInferenceError


Seconds = NewType("Seconds", float)
JobUUID = NewType("JobUUID", str)

if TYPE_CHECKING:
    from ..results import Results
    from .jobs import Jobs


class RemoteJobConstants:
    """Constants for remote job handling."""

    REMOTE_JOB_POLL_INTERVAL = 4
    REMOTE_JOB_VERBOSE = False
    DISCORD_URL = "https://discord.com/invite/mxAYkjfy9m"


@dataclass
class RemoteJobInfo:
    creation_data: RemoteInferenceCreationInfo
    job_uuid: JobUUID
    logger: JobLogger


class JobsRemoteInferenceHandler:
    def __init__(
        self,
        jobs: "Jobs",
        verbose: bool = RemoteJobConstants.REMOTE_JOB_VERBOSE,
        poll_interval: Seconds = RemoteJobConstants.REMOTE_JOB_POLL_INTERVAL,
    ):
        """Handles the creation and running of a remote inference job."""
        self.jobs = jobs
        self.verbose = verbose
        self.poll_interval = poll_interval

        from ..config import CONFIG

        self.expected_parrot_url = CONFIG.get("EXPECTED_PARROT_URL")
        self.remote_inference_url = f"{self.expected_parrot_url}/home/remote-inference"

    def _create_logger(self) -> JobLogger:
        from ..utilities import is_notebook
        from .jobs_remote_inference_logger import (
            StdOutJobLogger,
        )
        from .html_table_job_logger import HTMLTableJobLogger

        if is_notebook():
            return HTMLTableJobLogger(verbose=self.verbose)
        return StdOutJobLogger(verbose=self.verbose)

    def use_remote_inference(self, disable_remote_inference: bool) -> bool:
        import requests

        if disable_remote_inference:
            return False
        if not disable_remote_inference:
            try:
                from ..coop import Coop

                user_edsl_settings = Coop().edsl_settings
                return user_edsl_settings.get("remote_inference", False)
            except requests.ConnectionError:
                pass
            except CoopServerResponseError:
                pass

        return False

    def create_remote_inference_job(
        self,
        iterations: int = 1,
        remote_inference_description: Optional[str] = None,
        remote_inference_results_visibility: Optional["VisibilityType"] = "unlisted",
        fresh: Optional[bool] = False,
    ) -> RemoteJobInfo:
        from ..coop import Coop

        logger = self._create_logger()

        coop = Coop()
        logger.update(
            "Remote inference activated. Sending job to server...",
            status=JobsStatus.QUEUED,
        )
        remote_job_creation_data = coop.remote_inference_create(
            self.jobs,
            description=remote_inference_description,
            status="queued",
            iterations=iterations,
            initial_results_visibility=remote_inference_results_visibility,
            fresh=fresh,
        )
        logger.update(
            "Your survey is running at the Expected Parrot server...",
            status=JobsStatus.RUNNING,
        )
        job_uuid = remote_job_creation_data.get("uuid")
        logger.update(
            message=f"Job sent to server. (Job uuid={job_uuid}).",
            status=JobsStatus.RUNNING,
        )
        logger.add_info("job_uuid", job_uuid)

        logger.update(
            f"Job details are available at your Coop account. [Go to Remote Inference page]({self.remote_inference_url})",
            status=JobsStatus.RUNNING,
        )
        progress_bar_url = (
            f"{self.expected_parrot_url}/home/remote-job-progress/{job_uuid}"
        )
        logger.add_info("progress_bar_url", progress_bar_url)
        logger.update(
            f"View job progress [here]({progress_bar_url})", status=JobsStatus.RUNNING
        )

        return RemoteJobInfo(
            creation_data=remote_job_creation_data,
            job_uuid=job_uuid,
            logger=logger,
        )

    @staticmethod
    def check_status(
        job_uuid: JobUUID,
    ) -> "RemoteInferenceResponse":
        from ..coop import Coop

        coop = Coop()
        return coop.remote_inference_get(job_uuid)

    def _construct_remote_job_fetcher(
        self, testing_simulated_response: Optional[Any] = None
    ) -> Callable:
        if testing_simulated_response is not None:
            return lambda job_uuid: testing_simulated_response
        else:
            from ..coop import Coop

            coop = Coop()
            return coop.remote_inference_get

    def _construct_object_fetcher(
        self, testing_simulated_response: Optional[Any] = None
    ) -> Callable:
        "Constructs a function to fetch the results object from Coop."
        if testing_simulated_response is not None:
            return lambda results_uuid, expected_object_type: Results.example()
        else:
            from ..coop import Coop

            coop = Coop()
            return coop.get

    def _handle_cancelled_job(self, job_info: RemoteJobInfo) -> None:
        "Handles a cancelled job by logging the cancellation and updating the job status."

        job_info.logger.update(
            message="Job cancelled by the user.", status=JobsStatus.CANCELLED
        )
        job_info.logger.update(
            f"See [Remote Inference page]({self.expected_parrot_url}/home/remote-inference) for more details.",
            status=JobsStatus.CANCELLED,
        )

    def _handle_failed_job(
        self, job_info: RemoteJobInfo, remote_job_data: RemoteInferenceResponse
    ) -> None:
        "Handles a failed job by logging the error and updating the job status."
        latest_error_report_url = remote_job_data.get("latest_error_report_url")

        reason = remote_job_data.get("reason")

        if reason == "insufficient funds":
            job_info.logger.update(
                f"Error: Insufficient balance to start the job. Add funds to your account at the [Credits page]({self.expected_parrot_url}/home/credits)",
                status=JobsStatus.FAILED,
            )

        if latest_error_report_url:
            job_info.logger.add_info("error_report_url", latest_error_report_url)

        job_info.logger.update("Job failed.", status=JobsStatus.FAILED)
        job_info.logger.update(
            f"See [Remote Inference page]({self.expected_parrot_url}/home/remote-inference) for more details.",
            status=JobsStatus.FAILED,
        )
        job_info.logger.update(
            f"Need support? [Visit Discord]({RemoteJobConstants.DISCORD_URL})",
            status=JobsStatus.FAILED,
        )

    def _handle_partially_failed_job(
        self, job_info: RemoteJobInfo, remote_job_data: RemoteInferenceResponse
    ) -> None:
        "Handles a partially failed job by logging the error and updating the job status."
        latest_error_report_url = remote_job_data.get("latest_error_report_url")

        if latest_error_report_url:
            job_info.logger.add_info("error_report_url", latest_error_report_url)

        job_info.logger.update(
            "Job completed with partial results.", status=JobsStatus.PARTIALLY_FAILED
        )
        job_info.logger.update(
            f"See [Remote Inference page]({self.expected_parrot_url}/home/remote-inference) for more details.",
            status=JobsStatus.PARTIALLY_FAILED,
        )
        job_info.logger.update(
            f"Need support? [Visit Discord]({RemoteJobConstants.DISCORD_URL})",
            status=JobsStatus.PARTIALLY_FAILED,
        )

    def _sleep_for_a_bit(self, job_info: RemoteJobInfo, status: str) -> None:
        import time
        from datetime import datetime

        time_checked = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
        job_info.logger.update(
            f"Job status: {status} - last update: {time_checked}",
            status=JobsStatus.RUNNING,
        )
        time.sleep(self.poll_interval)

    def _fetch_results_and_log(
        self,
        job_info: RemoteJobInfo,
        job_status: Literal["failed", "partial_failed", "completed"],
        results_uuid: str,
        remote_job_data: RemoteInferenceResponse,
        object_fetcher: Callable,
    ) -> "Results":
        "Fetches the results object and logs the results URL."
        job_info.logger.add_info("results_uuid", results_uuid)
        results = object_fetcher(results_uuid, expected_object_type="results")
        results_url = remote_job_data.get("results_url")
        job_info.logger.add_info("results_url", results_url)

        if job_status == "completed":
            job_info.logger.update(
                f"Job completed and Results stored on Coop. [View Results]({results_url})",
                status=JobsStatus.COMPLETED,
            )
        elif job_status == "partial_failed":
            job_info.logger.update(
                f"View partial results [here]({results_url})",
                status=JobsStatus.PARTIALLY_FAILED,
            )
        results.job_uuid = job_info.job_uuid
        results.results_uuid = results_uuid
        return results

    def _attempt_fetch_job(
        self,
        job_info: RemoteJobInfo,
        remote_job_data_fetcher: Callable,
        object_fetcher: Callable,
    ) -> Union[None, "Results", Literal["continue"]]:
        """Makes one attempt to fetch and process a remote job's status and results."""
        remote_job_data = remote_job_data_fetcher(job_info.job_uuid)
        status = remote_job_data.get("status")
        reason = remote_job_data.get("reason")
        if status == "cancelled":
            self._handle_cancelled_job(job_info)
            return None, reason

        elif status == "failed" or status == "completed" or status == "partial_failed":
            if status == "failed":
                self._handle_failed_job(job_info, remote_job_data)
            elif status == "partial_failed":
                self._handle_partially_failed_job(job_info, remote_job_data)

            results_uuid = remote_job_data.get("results_uuid")
            if results_uuid:
                results = self._fetch_results_and_log(
                    job_info=job_info,
                    job_status=status,
                    results_uuid=results_uuid,
                    remote_job_data=remote_job_data,
                    object_fetcher=object_fetcher,
                )
                return results, reason
            else:
                return None, reason

        else:
            self._sleep_for_a_bit(job_info, status)
            return "continue", reason

    def poll_remote_inference_job(
        self,
        job_info: RemoteJobInfo,
        testing_simulated_response=None,
    ) -> Union[None, "Results"]:
        """Polls a remote inference job for completion and returns the results."""

        remote_job_data_fetcher = self._construct_remote_job_fetcher(
            testing_simulated_response
        )
        object_fetcher = self._construct_object_fetcher(testing_simulated_response)

        job_in_queue = True
        while job_in_queue:
            result, reason = self._attempt_fetch_job(
                job_info, remote_job_data_fetcher, object_fetcher
            )
            if result != "continue":
                return result, reason

    async def create_and_poll_remote_job(
        self,
        iterations: int = 1,
        remote_inference_description: Optional[str] = None,
        remote_inference_results_visibility: Optional[VisibilityType] = "unlisted",
    ) -> Union["Results", None]:
        """
        Creates and polls a remote inference job asynchronously.
        Reuses existing synchronous methods but runs them in an async context.

        :param iterations: Number of times to run each interview
        :param remote_inference_description: Optional description for the remote job
        :param remote_inference_results_visibility: Visibility setting for results
        :return: Results object if successful, None if job fails or is cancelled
        """
        import asyncio
        from functools import partial

        # Create job using existing method
        loop = asyncio.get_event_loop()
        job_info = await loop.run_in_executor(
            None,
            partial(
                self.create_remote_inference_job,
                iterations=iterations,
                remote_inference_description=remote_inference_description,
                remote_inference_results_visibility=remote_inference_results_visibility,
            ),
        )
        if job_info is None:
            raise RemoteInferenceError("Remote job creation failed.")

        return await loop.run_in_executor(
            None,
            partial(self.poll_remote_inference_job, job_info),
        )


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
